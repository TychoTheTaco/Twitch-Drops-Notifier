import argparse
import datetime
import json
import logging
from pathlib import Path

from google.cloud import firestore

from twitch_drops_watchdog.notifiers.notifier import BufferedNotifier
from twitch_drops_watchdog.twitch import DropCampaign, Client, Game
from twitch_drops_watchdog.twitch_drops_watchdog import Database, TwitchDropsWatchdog
from web_service.notifiers.email import FirestoreEmailSubscriberIterator, WebServiceEmailNotifier


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


class FirestoreDatabase(Database):

    def __init__(self, firestore_client: firestore.Client):
        self._firestore_client = firestore_client

    def load(self):
        pass

    def save(self):
        pass

    def add_campaign(self, campaign: DropCampaign) -> bool:
        return self._add_or_update_document(self._firestore_client.collection('campaigns').document(campaign['id']), campaign)

    def remove_campaign(self, campaign_id: str):
        self._firestore_client.collection('campaigns').document(campaign_id).delete()

    def add_game(self, game: Game) -> bool:
        return self._add_or_update_document(self._firestore_client.collection('games').document(game['id']), game)

    def get_campaigns(self):
        campaign_dictionary = {}
        for document_snapshot in self._firestore_client.collection('campaigns').stream():
            d = document_snapshot.to_dict()
            campaign_dictionary[d['id']] = d
        return campaign_dictionary.items()

    def _add_or_update_document(self, document_reference, data):
        document_snapshot = document_reference.get()

        # If this document already exists in our database, check if it changed
        if document_snapshot.exists:
            before = document_snapshot.to_dict()
            document_reference.update(data)
            after = document_reference.get().to_dict()
            if before != after:
                logger.debug('Document data changed!')
            return False

        # Add a 'created' field to the document so we know when it was added to the database
        data['created'] = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()

        # Add document to database
        document_reference.set(data)
        return True


def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--twitch-credentials',
                        help='The path to the credentials to use when interacting with the Twitch API.',
                        dest='twitch_credentials',
                        default='twitch.json')
    parser.add_argument('--email-credentials',
                        help='The path to the credentials for the email account used to send email notifications.',
                        dest='email_credentials',
                        default='email.json')
    parser.add_argument('--polling-interval',
                        help='The number of minutes to wait in between requests for new drop campaigns.',
                        dest='polling_interval',
                        default=15,
                        type=int)
    args = parser.parse_args()

    # Load Twitch credentials
    with open(args.twitch_credentials, 'r') as file:
        twitch_credentials = json.load(file)

    # Create Twitch client
    oauth_token = twitch_credentials['oauth_token']
    user_id = twitch_credentials['user_id']
    twitch_client = Client(client_id=Client.CLIENT_ID_TV, oath_token=oauth_token, user_id=user_id)

    # Create Firestore client
    firestore_client = firestore.Client()

    # Create watchdog
    watchdog = TwitchDropsWatchdog(
        twitch_client,
        polling_interval_minutes=args.polling_interval,
        database=FirestoreDatabase(firestore_client)
    )

    # Create email notifier
    with open(args.email_credentials) as file:
        email_credentials = json.load(file)
    email_notifier = WebServiceEmailNotifier(
        email_credentials['user'],
        email_credentials['password'],
        Path(__file__, '..', 'email_templates'),
        firestore_client
    )
    email_notifier.subscribe(FirestoreEmailSubscriberIterator(firestore_client))

    # Add notifiers
    def on_new_games(games):
        for item in games:
            email_notifier.on_new_game(item)
        if isinstance(email_notifier, BufferedNotifier):
            email_notifier.send_all_events()

    def on_new_campaigns(campaigns):
        for item in campaigns:
            email_notifier.on_new_drop_campaign(item)
        if isinstance(email_notifier, BufferedNotifier):
            email_notifier.send_all_events()

    watchdog.add_on_new_games_listener(on_new_games)
    watchdog.add_on_new_campaigns_listener(on_new_campaigns)

    # Start watchdog
    watchdog.start()


if __name__ == '__main__':
    main()
