import datetime
import logging
import time

from .twitch import Client

# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def _call_all(callables, parameters):
    for f in callables:
        try:
            f(parameters)
        except Exception as e:
            logger.exception('Exception occurred while calling listener!', exc_info=e)


class TwitchDropsWatchdog:
    """
    This class is used to poll the Twitch API at regular intervals to check for new Drops campaigns.
    """

    def __init__(self, twitch_api_client: Client, polling_interval_minutes: int = 15):
        self._twitch_api_client = twitch_api_client
        self._polling_interval_minutes = polling_interval_minutes

        self._drop_campaigns: {str: {}} = {}
        self._games = {str: {}}

        self._on_new_campaigns_listeners = []
        self._on_new_games_listeners = []

    def start(self):
        while True:

            try:
                self._update()
            except Exception as e:
                logger.exception('Failed to update Drops campaigns!', exc_info=e)

            # Sleep
            logger.info(f'Sleeping for {self._polling_interval_minutes} minutes...')
            time.sleep(self._polling_interval_minutes * 1000 * 60)

    def _update(self):
        # Remove expired campaigns from database
        for key, value in list(self._drop_campaigns.items()):
            end_date = get_datetime(value['endAt'])
            if end_date < datetime.datetime.now(datetime.timezone.utc):
                del self._drop_campaigns[key]

        # Get all drop campaigns
        logger.info('Fetching campaigns...')
        campaigns = self._twitch_api_client.get_drop_campaigns()
        logger.info(f'Found {len(campaigns)} campaigns.')

        # Update drop campaign database and find new campaigns
        logger.info('Updating database...')
        new_campaigns = []
        new_games = []
        for campaign in campaigns:

            # Ignore campaigns that have already ended
            if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                continue

            # Get campaign details
            try:
                campaign = self._twitch_api_client.get_drop_campaign_details([campaign['id']])[0]
            except Exception as e:
                logger.error('Error getting drop campaign details!', exc_info=e)
                continue

            # Check for new campaigns
            if campaign['id'] not in self._drop_campaigns:
                logger.info('New campaign: ' + campaign['game']['displayName'] + ' ' + campaign['name'])
                new_campaigns.append(campaign)
            self._drop_campaigns[campaign['id']] = campaign

            # Check for new games
            game = campaign['game']
            if game['id'] not in self._games:
                logger.info('New game: ' + game['displayName'])
                new_games.append(game)
            self._games[game['id']] = game

        # Notify listeners
        if len(new_campaigns) > 0:
            _call_all(self._on_new_campaigns_listeners, list(new_campaigns))
        if len(new_games) > 0:
            _call_all(self._on_new_games_listeners, list(new_games))

    def add_on_new_campaigns_listener(self, listener):
        self._on_new_campaigns_listeners.append(listener)

    def add_on_new_games_listener(self, listener):
        self._on_new_games_listeners.append(listener)
