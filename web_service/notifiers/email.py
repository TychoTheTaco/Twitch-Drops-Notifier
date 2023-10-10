import datetime
import logging
from pathlib import Path
from typing import Iterator

import pytz
from google.cloud import firestore
from jinja2.filters import FILTERS

from twitch_drops_watchdog.notifiers.email import EmailSubscriberIterator, EmailSubscriber, EmailNotifier
from twitch_drops_watchdog.notifiers.notifier import EventMapType

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


class FirestoreEmailSubscriberIterator(EmailSubscriberIterator):
    """
    Load email recipient data from Firestore.
    """

    def __init__(self, firestore_client: firestore.Client):
        self._firestore_client = firestore_client

    def __iter__(self) -> Iterator[EmailSubscriber]:
        for snapshot in self._firestore_client.collection('users').stream():
            user = snapshot.to_dict()
            events: EventMapType = {
                'new_drop_campaign': {
                    'games': user['games']
                }
            }
            if user['new_game_notifications']:
                events['new_game'] = {}
            yield EmailSubscriber(events, user['email'], timezone=user['timezone'])


class WebServiceEmailNotifier(EmailNotifier):

    def __init__(self, user: str, password: str, email_template_dir: str | Path, firestore_client: firestore.Client):
        super().__init__(user, password, email_template_dir)
        self._firestore_client = firestore_client
        self._start_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        self._domain = 'https://twitch-drops-bot.uw.r.appspot.com'

        # Listen for database changes
        self._firestore_client.collection('users').on_snapshot(self._on_snapshot_users)

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

    def _send_initial_email(self, user, campaigns):
        logger.info('Sending initial email to: ' + user['email'])
        body = self._jinja_environment.get_template('message_and_campaigns_list.html').render(
            user=user,
            domain=self._domain,
            campaigns=campaigns,
            message='You have subscribed to Twitch Drop Campaign notifications.'
        )
        self.send(user['email'], 'Active Twitch Drop Campaigns', body)

    def _send_update_email(self, user, campaigns):
        logger.info('Sending update email to: ' + user['email'])
        body = self._jinja_environment.get_template('message_and_campaigns_list.html').render(
            user=user,
            domain=self._domain,
            campaigns=campaigns,
            message='You recently updated your preferences.'
        )
        self.send(user['email'], 'Active Twitch Drop Campaigns', body)
