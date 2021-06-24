import datetime
import json
import logging
import argparse

from google.cloud import firestore

from .twitch_drops_watchdog import TwitchDropsWatchdog
from .firestore import FirestoreUpdater
from .email import EmailSender
from .utils import get_gmail_credentials


def logging_filter(record):
    """
    Filter logs so that only records from this module are shown.
    :param record:
    :return:
    """
    names = ['twitch_drops_watchdog', '__main__', 'twitch_drops_notifier']
    for name in names:
        if name in record.name or name in record.pathname:
            return True
    return False


# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s', level=logging.DEBUG, datefmt='%m/%d/%Y %H:%M:%S')
logging.getLogger().handlers[0].addFilter(logging_filter)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def get_active_subscribed_games(user):
    subscribed_games = []
    for campaign_document in firestore_client.collection('campaigns').list_documents():
        campaign = campaign_document.get().to_dict()

        # Ignore campaigns that have already ended
        if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
            continue

        if campaign['game']['id'] in user['games']:
            subscribed_games.append(campaign)
    return subscribed_games


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--twitch-credentials',
                        help='The path to the credentials to use when interacting with the Twitch API.',
                        dest='twitch_credentials',
                        default='twitch.json')
    parser.add_argument('--gmail-credentials',
                        help='The path to the credentials for the Gmail account used to send email notifications.',
                        dest='gmail_credentials',
                        default='gmail.json')
    parser.add_argument('--sleep-delay',
                        help='The number of seconds to wait in between requests for new drop campaigns.',
                        dest='sleep_delay',
                        default=60 * 60 * 1,
                        type=int)
    args = parser.parse_args()

    # Load Twitch credentials
    with open(args.twitch_credentials, 'r') as file:
        twitch_credentials = json.load(file)

    # Get Gmail credentials and create service
    gmail_credentials = get_gmail_credentials('credentials/gmail.pickle', args.gmail_credentials)

    email_sender = EmailSender(gmail_credentials)

    started_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    firestore_client = firestore.Client()

    def on_users_snapshot(documents, changes, read):
        for change in changes:
            d = change.document.to_dict()
            logger.debug('USER change: ' + change.type.name + ' ' + d['email'])
            if change.type.name == 'ADDED':

                # Ignore documents that were created before this script was started
                created_time = datetime.datetime.fromisoformat(d['created'])
                if created_time < started_time:
                    continue

                email_sender.send_initial_email(d, get_active_subscribed_games(d))

            elif change.type.name == 'MODIFIED':
                email_sender.send_update_email(d, get_active_subscribed_games(d))
            elif change.type.name == 'REMOVED':
                pass

    def on_games_snapshot(documents, changes, read):
        new_games = []
        for change in changes:
            d = change.document.to_dict()
            logger.debug('GAME change: ' + change.type.name + ' ' + d['displayName'])
            if change.type.name == 'ADDED':

                if 'created' not in d:
                    d['created'] = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()
                    change.document.reference.set(d)
                    continue

                # Ignore documents that were created before this script was started
                created_time = datetime.datetime.fromisoformat(d['created'])
                if created_time < started_time:
                    continue

                new_games.append(d)

        if len(new_games) > 0:
            for document_reference in firestore_client.collection('users').list_documents():
                email_sender.send_new_games_email(document_reference.get().to_dict(), new_games)

    firestore_client.collection('users').on_snapshot(on_users_snapshot)

    # Listen to game changes
    firestore_client.collection('games').on_snapshot(on_games_snapshot)

    # Start bot
    bot = TwitchDropsWatchdog(twitch_credentials)
    bot.add_on_new_campaigns_listener(FirestoreUpdater().on_new_campaigns)
    bot.add_on_new_campaigns_listener(email_sender.on_new_campaigns)
    bot.start()
