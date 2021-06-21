import datetime
import logging
import time
from typing import Callable

from tinydb import TinyDB

from . import twitch

# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


class TwitchDropsWatchdog:
    """
    This class is used to poll the Twitch API at regular intervals to check for
    new "Drop Campaigns". Whenever new campaigns are found, they get added to a
    local database and all attached listeners are called.
    """

    def __init__(self, credentials, sleep_delay_seconds: int = 60 * 60 * 1, database_path='database.json'):
        """
        Creates a new TwitchDropsWatchdog.
        :param credentials: A dictionary containing the required credentials to use the Twitch API. The following are required:
        {
          "client_id": str,
          "oauth_token": str,
          "channel_login": str
        }
        :param sleep_delay_seconds: The number of seconds to wait in between polling the Twitch API. Since new campaigns are not added very
        often, this can be set to a few hours.
        :param database_path: A path to the local database of campaigns.
        """
        self._credentials = credentials
        self._sleep_delay_seconds = sleep_delay_seconds
        self._database = TinyDB(database_path)

        self._on_new_campaigns_listeners = []

    @staticmethod
    def _table_contains(table, item):
        for x in table:
            if x == item:
                return True
        return False

    def start(self):
        while True:

            # Get all drop campaigns
            logger.info('Updating campaign list...')
            campaigns = twitch.get_drop_campaigns(self._credentials)
            logger.info(f'Found {len(campaigns)} campaigns.')

            # Update drop campaign database and find new campaigns
            new_campaigns = []
            for campaign in campaigns:

                # Ignore campaigns that have already ended
                if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                    continue

                table = self._database.table('campaigns')

                # Ignore campaigns that are already in the database
                if self._table_contains(table, campaign):
                    continue

                # Add campaign to database
                table.insert(campaign)
                new_campaigns.append(campaign)
                logger.info('New campaign: ' + campaign['game']['displayName'] + ' | ' + campaign['name'])

            # Notify listeners
            if len(new_campaigns) > 0:
                for listener in self._on_new_campaigns_listeners:
                    listener(list(new_campaigns))

            # Sleep
            logger.info(f'Sleeping for {self._sleep_delay_seconds} seconds...')
            time.sleep(self._sleep_delay_seconds)

    def add_on_new_campaigns_listener(self, callback: Callable):
        self._on_new_campaigns_listeners.append(callback)
