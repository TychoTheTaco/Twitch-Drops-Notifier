import base64
import datetime
import logging
from email.mime.text import MIMEText
import smtplib

import pytz
from google.cloud import firestore
from jinja2 import Environment, FileSystemLoader
from jinja2.filters import FILTERS

from .twitch_drops_watchdog import TwitchDropsWatchdog


# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def convert_time(value, user):
    try:
        value = get_datetime(value).astimezone(pytz.timezone(user['timezone']))
    except pytz.exceptions.UnknownTimeZoneError:
        pass
    return value.strftime('%d %B %Y %H:%M %Z')


FILTERS['convert_time'] = convert_time


class EmailSender:

    def __init__(self, credentials, firestore_client: firestore.Client, watchdog: TwitchDropsWatchdog):
        self._credentials = credentials

        self._firestore_client = firestore_client

        self._start_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        self._domain = 'https://twitch-drops-bot.uw.r.appspot.com'

        self._jinja_environment = Environment(loader=FileSystemLoader('email_templates'))

        # Listen for database changes
        firestore_client.collection('users').on_snapshot(self._on_snapshot_users)

        watchdog.add_on_new_games_listener(self._on_new_games)
        watchdog.add_on_new_campaign_details_listener(self._on_new_campaign_details)

        self._refresh_count = 0

    def _get_active_subscribed_games(self, user):
        subscribed_games = []
        for campaign_document in self._firestore_client.collection('campaign_details').list_documents():
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
                try:
                    self._send_initial_email(user, self._get_active_subscribed_games(user))
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

            elif change.type.name == 'MODIFIED':

                logger.debug('User modified: ' + user['email'])
                try:
                    self._send_update_email(user, self._get_active_subscribed_games(user))
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

            elif change.type.name == 'REMOVED':

                logger.debug('User removed: ' + user['email'])

    def _on_new_games(self, games):
        # Send new game emails
        for snapshot in self._firestore_client.collection('users').stream():
            user = snapshot.to_dict()
            if user.get('new_game_notifications', True):
                try:
                    self._send_new_games_email(user, games)
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

    def _on_new_campaign_details(self, campaigns):
        # Send new campaign emails
        for snapshot in self._firestore_client.collection('users').stream():
            user = snapshot.to_dict()

            # Get campaigns that the user is subscribed to
            subscribed_campaigns = []
            for campaign in campaigns:
                if len(user['games']) == 0 or campaign['game']['id'] in user['games']:
                    subscribed_campaigns.append(campaign)

            # Send new campaigns email
            if len(subscribed_campaigns) > 0:
                try:
                    self._send_new_campaigns_email(user, subscribed_campaigns)
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

    def _send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = 'twitchdropsbot@gmail.com'
        message['subject'] = subject

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(self._credentials['user'], self._credentials['password'])
        server.send_message(message)
        server.quit()

    def _send_new_campaigns_email(self, user, campaigns):
        logger.info('Sending new campaigns email to: ' + user['email'])
        body = self._jinja_environment.get_template('new_campaigns.html').render(
            user=user,
            domain=self._domain,
            campaigns=campaigns
        )
        self._send(user['email'], 'New Twitch Drop Campaigns!', body)

    def _send_initial_email(self, user, campaigns):
        logger.info('Sending initial email to: ' + user['email'])
        body = self._jinja_environment.get_template('message_and_campaigns_list.html').render(
            user=user,
            domain=self._domain,
            campaigns=campaigns,
            message='You have subscribed to Twitch Drop Campaign notifications.'
        )
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)

    def _send_update_email(self, user, campaigns):
        logger.info('Sending update email to: ' + user['email'])
        body = self._jinja_environment.get_template('message_and_campaigns_list.html').render(
            user=user,
            domain=self._domain,
            campaigns=campaigns,
            message='You recently updated your preferences.'
        )
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)

    def _send_new_games_email(self, user, games):
        logger.info('Sending new games email to: ' + user['email'])
        body = self._jinja_environment.get_template('new_games.html').render(
            user=user,
            domain=self._domain,
            games=games
        )
        self._send(user['email'], 'New Games', body)
