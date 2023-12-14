import datetime
import uuid
from typing import Optional, Dict, Any

from flask import Flask, render_template, request
from google.cloud import firestore
import pytz
from google.cloud.firestore_v1 import FieldFilter, DocumentSnapshot


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


app = Flask(__name__)

firestore_client = firestore.Client()
firestore_client.collection('games').on_snapshot(lambda documents, changes, read_time: update_games_cache())

games_cache = []


def update_games_cache():
    print('Updating games cache...')
    games_cache.clear()
    for document in firestore_client.collection('games').stream():
        d = document.to_dict()
        games_cache.append(d)


def get_user_document(user_id: str) -> Optional[DocumentSnapshot]:
    for document in firestore_client.collection('users').where(filter=FieldFilter('id', '==', user_id)).stream():
        return document
    return None


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    document = get_user_document(user_id)
    if document:
        return document.to_dict()
    return None


@app.route("/_ah/warmup")
def warmup():
    """Served stub function returning no content.

    Your warmup logic can be implemented here (e.g. set up a database connection pool)

    Returns:
        An empty string, an HTTP code 200, and an empty object.
    """
    return "", 200, {}


@app.route('/')
def index():
    # Find user
    user_id = request.args.get('id', None)
    user = get_user(user_id)

    # Games
    games = list(sorted(games_cache, key=lambda x: x['displayName']))

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
    user = get_user(request.args.get('id'))
    if not user:
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
    user_document = get_user_document(request.args.get('id'))
    if not user_document:
        return render_template('error.html', message='This user is not subscribed.')

    user_document.reference.delete()

    return render_template('success.html', message='You have been unsubscribed')


if __name__ == '__main__':
    update_games_cache()
    app.run('localhost')
