import threading
import datetime

from flask import Flask, render_template, request
from google.cloud import firestore
import pytz
import uuid


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


app = Flask(__name__)

firestore_client = firestore.Client()


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
        'id': str(uuid.uuid4()),
        'created': datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()
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

    # Update timezone
    user['timezone'] = request.form['timezone']

    # Update firestore document
    firestore_client.collection('users').document(user['email']).set(user)

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


if __name__ == '__main__':
    app.run('localhost')
