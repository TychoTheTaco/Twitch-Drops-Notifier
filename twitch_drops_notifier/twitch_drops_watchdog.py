import datetime
import logging
import time
from pprint import pprint

from google.cloud import firestore
from deepdiff import DeepDiff

from . import twitch
from . import utils

# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def save_changes(before, after):
    with open(before['id'] + '.json', 'w') as file:
        d = DeepDiff(before, after)
        pprint(d, file)


class TwitchDropsWatchdog:
    """
    This class is used to poll the Twitch API at regular intervals to check for
    new "Drop Campaigns".
    """

    def __init__(self, twitch_credentials, firestore_client: firestore.Client, sleep_delay_seconds: int = 60 * 60 * 1):
        """
        Creates a new TwitchDropsWatchdog.
        :param twitch_credentials: A dictionary containing the required credentials to use the Twitch API. The following are required:
        {
          "client_id": str,
          "oauth_token": str,
          "channel_login": str
        }
        :param firestore_client:
        :param sleep_delay_seconds: The number of seconds to wait in between polling the Twitch API. Since new campaigns are not added very
        often, this can be set to a few hours.
        """
        self._twitch_credentials = twitch_credentials
        self._firestore_client = firestore_client
        self._sleep_delay_seconds = sleep_delay_seconds

    def _add_or_update_campaign(self, campaign):
        document_reference = self._firestore_client.collection('campaigns').document(campaign['id'])
        document_snapshot = document_reference.get()

        # If this campaign already exists in our database, check if it changed
        if document_snapshot.exists:
            before = document_snapshot.to_dict()
            document_reference.update(campaign)
            after = document_reference.get().to_dict()
            if before != after:
                logger.debug('Campaign changed: ' + campaign['game']['displayName'] + ' ' + campaign['id'])
                save_changes(before, after)
            return

        # Add a 'created' field to the campaign object so we know when it was added to the database
        campaign['created'] = utils.get_timestamp()

        # Add campaign to database
        document_reference.set(campaign)
        logger.info('New campaign: ' + campaign['game']['displayName'] + ' | ' + campaign['name'])

    def _add_or_update_campaign_details(self, campaign):
        document_reference = self._firestore_client.collection('campaign_details').document(campaign['id'])
        document_snapshot = document_reference.get()

        # If this campaign already exists in our database, check if it changed
        if document_snapshot.exists:
            before = document_snapshot.to_dict()
            document_reference.update(campaign)
            after = document_reference.get().to_dict()
            if before != after:
                logger.debug('Campaign details changed: ' + campaign['game']['displayName'] + ' ' + campaign['id'])
                save_changes(before, after)
            return

        # Add a 'created' field to the campaign object so we know when it was added to the database
        campaign['created'] = utils.get_timestamp()

        # Add campaign to database
        document_reference.set(campaign)
        logger.info('New campaign details: ' + campaign['game']['displayName'] + ' | ' + campaign['name'])

    def _add_or_update_game(self, game):
        document_reference = self._firestore_client.collection('games').document(game['id'])
        document_snapshot = document_reference.get()

        # If this game already exists in our database, check if it changed
        if document_snapshot.exists:
            before = document_snapshot.to_dict()
            document_reference.update(game)
            after = document_reference.get().to_dict()
            if before != after:
                logger.debug('Game details changed! Before: ' + str(before) + ' After: ' + str(after))
            return

        # Add a 'created' field to the game object so we know when it was added to the database
        game['created'] = utils.get_timestamp()

        # Add game to database
        document_reference.set(game)
        logger.info('New game: ' + game['displayName'])

    def start(self):
        while True:

            # Get all drop campaigns
            logger.info('Updating campaign list...')
            campaigns = twitch.get_drop_campaigns(self._twitch_credentials)
            logger.info(f'Found {len(campaigns)} campaigns.')

            # Update drop campaign database and find new campaigns
            logger.info('Updating database...')
            for campaign in campaigns:

                # Ignore campaigns that have already ended
                if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                    continue

                # Get campaign details
                campaign_details = twitch.get_drop_campaign_details(self._twitch_credentials, [campaign['id']])[0]

                # Update database
                self._add_or_update_campaign(campaign)
                self._add_or_update_campaign_details(campaign_details)
                self._add_or_update_game(campaign['game'])

            # Sleep
            logger.info(f'Sleeping for {self._sleep_delay_seconds} seconds...')
            time.sleep(self._sleep_delay_seconds)
