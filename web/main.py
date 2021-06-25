import datetime
import uuid

from flask import Flask, render_template, request
from google.cloud import firestore
import pytz


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


app = Flask(__name__)

firestore_client = firestore.Client()


@app.route('/')
def index():
    # Find user
    user = None
    user_id = request.args.get('id', None)
    if user_id is not None:
        for document in firestore_client.collection('users').list_documents():
            d = document.get().to_dict()
            if d['id'] == user_id:
                user = d
                break

    # Games
    games = []
    for game_document in firestore_client.collection('games').list_documents():
        games.append(game_document.get().to_dict())
    games = list(sorted(games, key=lambda x: x['displayName']))

    # Timezones
    timezones = pytz.common_timezones

    return render_template('index.html', user=user, games=games, timezones=timezones)


@app.route('/subscribe', methods=['POST'])
def subscribe():

    # Make sure email is valid
    if 'email' not in request.form or len(request.form['email']) <= 1:
        return render_template('error.html', message='Invalid email.')

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
        'id': str(uuid.uuid4()),
        'created': datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat(),
        'new_game_notifications': request.form.get('new_game_notifications', 'off') == 'on'
    }

    firestore_client.collection('users').document(user['email']).set(user)

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

    # Update new games notification
    user['new_game_notifications'] = request.form.get('new_game_notifications', 'off') == 'on'

    # Update timezone
    user['timezone'] = request.form['timezone']

    # Update firestore document
    firestore_client.collection('users').document(user['email']).set(user)

    return render_template('success.html', message='Preferences updated!')


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


if __name__ == '__main__':
    app.run('localhost')
