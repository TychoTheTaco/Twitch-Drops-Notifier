from flask import Flask, render_template, request
from google.cloud import firestore
import pytz
import threading

from twitch_drops_notifier.email import EmailSender
from twitch_drops_notifier.utils import get_gmail_credentials


def create_app(gmail_credentials_path: str):
    app = Flask(__name__)

    firestore_client = firestore.Client()

    email_sender = EmailSender(get_gmail_credentials('../credentials/gmail.pickle', gmail_credentials_path))

    @app.route('/')
    def index():

        # Games
        games = []
        for game_document in firestore_client.collection('games').list_documents():
            games.append(game_document.get().to_dict())
        games = list(sorted(games, key=lambda x: x['displayName']))

        # Timezones
        timezones = pytz.common_timezones

        return render_template('index.html', games=games, timezones=timezones)

    def send_initial_email(user):
        subscribed_games = []
        # TODO: Ignore/remove campaigns that ended
        for campaign_document in firestore_client.collection('campaigns').list_documents():
            campaign = campaign_document.get().to_dict()
            if campaign['game']['id'] in user['games']:
                subscribed_games.append(campaign)
        email_sender.send_initial_email(user, subscribed_games)

    @app.route('/subscribe', methods=['POST'])
    def subscribe():
        games = []
        for key, value in request.form.items():
            if key.startswith('game_'):
                games.append(key.split('game_')[1])

        user = {
            'email': request.form['email'],
            'games': games,
            'timezone': request.form['timezone']
        }

        firestore_client.collection('users').document(user['email']).set(user)

        # Send initial email
        threading.Thread(target=send_initial_email, args=(user,)).start()

        return render_template('subscribe_result.html')

    return app


if __name__ == '__main__':
    app = create_app('credentials/gmail.json')
    app.run('localhost')
