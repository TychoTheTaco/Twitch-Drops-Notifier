import threading
import datetime

from flask import Flask, render_template, request
from google.cloud import firestore
import pytz
import uuid

from twitch_drops_notifier.email import EmailSender
from twitch_drops_notifier.utils import get_gmail_credentials


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


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
        for campaign_document in firestore_client.collection('campaigns').list_documents():
            campaign = campaign_document.get().to_dict()

            # Ignore campaigns that have already ended
            if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                continue

            if campaign['game']['id'] in user['games']:
                subscribed_games.append(campaign)

        email_sender.send_initial_email(user, subscribed_games)

    def send_update_email(user):
        subscribed_games = []
        for campaign_document in firestore_client.collection('campaigns').list_documents():
            campaign = campaign_document.get().to_dict()

            # Ignore campaigns that have already ended
            if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                continue

            if campaign['game']['id'] in user['games']:
                subscribed_games.append(campaign)

        email_sender.send_update_email(user, subscribed_games)

    @app.route('/subscribe', methods=['POST'])
    def subscribe():

        # Make sure this user is not already subscribed
        if firestore_client.collection('users').document(request.form['email']).get().exists:
            return render_template('error.html', message='This user is already subscribed!')

        games = []
        for key, value in request.form.items():
            if key.startswith('game_'):
                games.append(key.split('game_')[1])

        user = {
            'email': request.form['email'],
            'games': games,
            'timezone': request.form['timezone'],
            'id': str(uuid.uuid4())
        }

        firestore_client.collection('users').document(user['email']).set(user)

        # Send initial email
        threading.Thread(target=send_initial_email, args=(user,)).start()

        return render_template('success.html', message='You have subscribed to notifications!')

    @app.route('/update', methods=['POST'])
    def update():

        # Find user
        for document in firestore_client.collection('users').list_documents():
            d = document.get().to_dict()
            if d['id'] == request.args.get('id'):
                user = d
                break
        else:
            return render_template('error.html', message='This user is not subscribed.')

        # Update games
        games = []
        for key, value in request.form.items():
            if key.startswith('game_'):
                games.append(key.split('game_')[1])
        user['games'] = games

        # Update timezone
        user['timezone'] = request.form['timezone']

        # Update firestore document
        firestore_client.collection('users').document(user['email']).set(user)

        # Send update email
        threading.Thread(target=send_update_email, args=(user,)).start()

        return render_template('success.html', message='Preferences updated!')

    @app.route('/edit', methods=['GET'])
    def edit():

        # Find user
        for document in firestore_client.collection('users').list_documents():
            d = document.get().to_dict()
            if d['id'] == request.args.get('id'):
                user = d
                break
        else:
            return render_template('error.html', message='This user is not subscribed!')

        # Games
        games = []
        for game_document in firestore_client.collection('games').list_documents():
            games.append(game_document.get().to_dict())
        games = list(sorted(games, key=lambda x: x['displayName']))

        # Timezones
        timezones = pytz.common_timezones

        return render_template('edit.html', games=games, timezones=timezones, user=user)

    @app.route('/unsubscribe', methods=['GET'])
    def unsubscribe():
        for document in firestore_client.collection('users').list_documents():
            d = document.get().to_dict()
            if d['id'] == request.args.get('id'):
                document.delete()
                break
        else:
            return render_template('error.html', message='This user is not subscribed.')

        return render_template('success.html', message='You have been unsubscribed')

    return app


if __name__ == '__main__':
    app = create_app('../credentials/gmail.json')
    app.run('localhost')
