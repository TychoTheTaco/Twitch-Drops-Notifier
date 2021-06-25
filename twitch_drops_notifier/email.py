import base64
import datetime
import urllib.parse
import logging
from email.mime.text import MIMEText

import pytz
from googleapiclient.discovery import build
from google.cloud import firestore


# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def format_campaigns_list(user, campaigns):
    text = ''
    for campaign in sorted(campaigns, key=lambda x: get_datetime(x['endAt'])):
        start_time = get_datetime(campaign['startAt'])
        end_time = get_datetime(campaign['endAt'])

        # Convert start and end times to user-specified timezone
        if 'timezone' in user:
            try:
                start_time_local = start_time.astimezone(pytz.timezone(user['timezone']))
                end_time_local = end_time.astimezone(pytz.timezone(user['timezone']))
                start_time = start_time_local
                end_time = end_time_local
            except pytz.exceptions.UnknownTimeZoneError:
                pass

        text += f'<b>{campaign["game"]["displayName"]}</b><br>{campaign["name"]}<br>'
        text += 'Starts: ' + start_time.strftime('%d %B %Y %H:%M %Z') + '<br>'
        text += 'Ends  : ' + end_time.strftime('%d %B %Y %H:%M %Z') + '<br>'
        text += f'<a href="https://www.twitch.tv/directory/game/{urllib.parse.quote(campaign["game"]["displayName"])}?tl=c2542d6d-cd10-4532-919b-3d19f30a768b">Watch now!</a>'
        text += '<br><br>'
    return text


def format_games_list(user, games):
    text = ''
    for game in sorted(games, key=lambda x: x['displayName']):
        text += f'<b>{game["displayName"]}</b><br>'
        text += '<br><br>'
    return text


class EmailSender:

    def __init__(self, gmail_credentials, firestore_client: firestore.Client):
        self._gmail_service = build('gmail', 'v1', credentials=gmail_credentials)
        self._firestore_client = firestore_client

        self._start_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        # Listen for database changes
        firestore_client.collection('users').on_snapshot(self._on_snapshot_users)
        firestore_client.collection('games').on_snapshot(self._on_snapshot_games)
        firestore_client.collection('campaigns').on_snapshot(self._on_snapshot_campaigns)

    def _get_active_subscribed_games(self, user):
        subscribed_games = []
        for campaign_document in self._firestore_client.collection('campaigns').list_documents():
            campaign = campaign_document.get().to_dict()

            # Ignore campaigns that have already ended
            if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                continue

            if campaign['game']['id'] in user['games']:
                subscribed_games.append(campaign)
        return subscribed_games

    def _on_snapshot_users(self, documents, changes, read):
        for change in changes:
            user = change.document.to_dict()
            if change.type.name == 'ADDED':

                # Ignore documents that were added before this script was started
                if datetime.datetime.fromisoformat(user['created']) < self._start_time:
                    continue

                logger.debug('User added: ' + user['email'])

                # Send initial email
                self._send_initial_email(user, self._get_active_subscribed_games(user))

            elif change.type.name == 'MODIFIED':

                logger.debug('User modified: ' + user['email'])
                self._send_update_email(user, self._get_active_subscribed_games(user))

            elif change.type.name == 'REMOVED':

                logger.debug('User removed: ' + user['email'])

    def _on_snapshot_games(self, documents, changes, read):
        new_games = []
        for change in changes:
            game = change.document.to_dict()
            if change.type.name == 'ADDED':

                # Ignore documents that were created before this script was started
                if datetime.datetime.fromisoformat(game['created']) < self._start_time:
                    continue

                logger.debug('Game added: ' + game['displayName'])
                new_games.append(game)

        # Send new game emails
        if len(new_games) > 0:
            for snapshot in self._firestore_client.collection('users').stream():
                user = snapshot.to_dict()
                if user.get('new_game_notifications', True):
                    self._send_new_games_email(user, new_games)
                    pass

    def _on_snapshot_campaigns(self, documents, changes, read):
        new_campaigns = []
        for change in changes:
            campaign = change.document.to_dict()
            if change.type.name == 'ADDED':

                # Ignore documents that were created before this script was started
                if datetime.datetime.fromisoformat(campaign['created']) < self._start_time:
                    continue

                logger.debug('Campaign added: ' + campaign['game']['displayName'] + ' ' + campaign['name'])
                new_campaigns.append(campaign)

        # Send new campaign emails
        if len(new_campaigns) > 0:
            for snapshot in self._firestore_client.collection('users').stream():
                user = snapshot.to_dict()

                # Get campaigns that the user is subscribed to
                subscribed_campaigns = []
                for campaign in new_campaigns:
                    if len(user['games']) == 0 or campaign['game']['id'] in user['games']:
                        subscribed_campaigns.append(campaign)

                # Send new campaigns email
                if len(subscribed_campaigns) > 0:
                    try:
                        self._send_new_campaigns_email(user, subscribed_campaigns)
                    except Exception as e:
                        logger.error('Failed to send email: ' + str(e))

    def _create_edit_and_unsubscribe_footer(self, user):
        domain = 'https://twitch-drops-bot.uw.r.appspot.com'
        content = f'<a href="{domain}?id={user["id"]}">Edit Preferences</a> | <a href="{domain}/unsubscribe?id={user["id"]}">Unsubscribe</a>'
        content += '<style></style>'
        return content

    def _send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = 'twitchdropsbot@gmail.com'
        message['subject'] = subject
        message = {'raw': base64.urlsafe_b64encode(message.as_string().encode('utf-8')).decode('utf-8')}
        self._gmail_service.users().messages().send(userId='me', body=message).execute()

    def _send_new_campaigns_email(self, user, campaigns):
        logger.info('Sending new campaigns email to: ' + user['email'])
        body = 'Here is a list of new Twitch Drop campaigns:<br><br>'
        body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'New Twitch Drop Campaigns!', body)

    def _send_initial_email(self, user, campaigns):
        logger.info('Sending initial email to: ' + user['email'])
        body = 'Thanks for subscribing! '
        if len(campaigns) == 0:
            body += 'There aren\'t any active drop campaigns for the games you selected, but you will be notified when a new one is found.<br><br>'
        else:
            body += 'Here is a list of currently active Twitch drop campaigns:<br><br>'
            body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)

    def _send_update_email(self, user, campaigns):
        logger.info('Sending update email to: ' + user['email'])
        body = 'You recently updated your preferences. Here is an updated list of active drop campaigns.<br><br>'
        if len(campaigns) == 0:
            body += 'No active campaigns.<br><br>'
        else:
            body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)

    def _send_new_games_email(self, user, games):
        logger.info('Sending new games email to: ' + user['email'])
        body = 'Some new games are available for notifications.<br><br>'
        body += format_games_list(user, games)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'New Games', body)
