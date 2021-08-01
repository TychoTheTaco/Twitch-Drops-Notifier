import datetime
import logging
import time

from google.cloud import firestore

from . import twitch
from . import utils

# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


class TwitchDropsWatchdog:
    """
    This class is used to poll the Twitch API at regular intervals to check for
    new "Drop Campaigns".
    """

    def __init__(self, twitch_credentials, firestore_client: firestore.Client, sleep_delay_seconds: int = 60 * 60 * 1):
        """
        Creates a new TwitchDropsWatchdog.
        :param twitch_credentials: A dictionary containing the required
        credentials to use the Twitch API. The following are required:
        {
          "client_id": str,
          "oauth_token": str,
          "channel_login": str
        }
        :param firestore_client:
        :param sleep_delay_seconds: The number of seconds to wait in between
        polling the Twitch API. Since new campaigns are not added very often,
        this can be set to a few hours.
        """
        self._twitch_credentials = twitch_credentials
        self._firestore_client = firestore_client
        self._sleep_delay_seconds = sleep_delay_seconds

        self._on_new_campaign_details_listeners = []
        self._on_new_games_listeners = []

    def _add_or_update_campaign_details(self, campaign):
        return self._add_or_update_document(self._firestore_client.collection('campaign_details').document(campaign['id']), campaign)

    def _add_or_update_game(self, game):
        return self._add_or_update_document(self._firestore_client.collection('games').document(game['id']), game)

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
        data['created'] = utils.get_timestamp()

        # Add document to database
        document_reference.set(data)
        return True

    def _call_all(self, callables, parameters):
        for f in callables:
            try:
                f(parameters)
            except Exception as e:
                logger.exception('Exception occurred while calling listener!', exc_info=e)

    def start(self):
        while True:

            # Get all drop campaigns
            logger.info('Updating campaign list...')
            campaigns = twitch.get_drop_campaigns(self._twitch_credentials)
            logger.info(f'Found {len(campaigns)} campaigns.')

            # Update drop campaign database and find new campaigns
            logger.info('Updating database...')
            new_campaign_details = []
            new_games = []
            for campaign in campaigns:

                # Ignore campaigns that have already ended
                if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                    continue

                # Get campaign details
                campaign_details = twitch.get_drop_campaign_details(self._twitch_credentials, [campaign['id']])[0]

                # Update database
                if self._add_or_update_campaign_details(campaign_details):
                    new_campaign_details.append(campaign_details)
                    logger.info('New campaign details: ' + campaign['game']['displayName'] + ' ' + campaign['name'])
                game = campaign['game']
                if self._add_or_update_game(game):
                    new_games.append(game)
                    logger.info('New game: ' + game['displayName'])

            # Notify listeners
            if len(new_campaign_details) > 0:
                self._call_all(self._on_new_campaign_details_listeners, list(new_campaign_details))
            if len(new_games) > 0:
                self._call_all(self._on_new_games_listeners, list(new_games))

            # Sleep
            logger.info(f'Sleeping for {self._sleep_delay_seconds} seconds...')
            time.sleep(self._sleep_delay_seconds)

    def add_on_new_campaign_details_listener(self, listener):
        self._on_new_campaign_details_listeners.append(listener)

    def add_on_new_games_listener(self, listener):
        self._on_new_games_listeners.append(listener)
