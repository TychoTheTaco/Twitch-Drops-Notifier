import datetime
import json
import logging
import time
from pathlib import Path
from typing import Set

from .twitch import Client, DropCampaign, Game

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


class Database:

    def __init__(self, path: str | Path):
        self._path = path
        self._data = {}

    def load(self):
        try:
            with open(self._path, 'r') as file:
                self._data = json.load(file)
        except FileNotFoundError:
            pass
        if 'campaigns' not in self._data:
            self._data['campaigns'] = {}
        if 'games' not in self._data:
            self._data['games'] = {}

    def save(self):
        with open(self._path, 'w') as file:
            json.dump(self._data, file, indent=4)

    def add_campaign(self, campaign: DropCampaign) -> bool:
        if campaign['id'] not in self._data['campaigns']:
            self._data['campaigns'][campaign['id']] = {'endAt': campaign['endAt']}
            return True
        return False

    def remove_campaign(self, campaign_id: str):
        del self._data['campaigns'][campaign_id]

    def add_game(self, game: Game) -> bool:
        if game['id'] not in self._data['games']:
            self._data['games'][game['id']] = {'displayName': game['displayName']}
            return True
        return False

    def get_campaigns(self):
        return self._data['campaigns'].items()


class TwitchDropsWatchdog:
    """
    This class is used to poll the Twitch API at regular intervals to check for new Drops campaigns.
    """

    def __init__(self, twitch_api_client: Client, polling_interval_minutes: int = 15):
        self._twitch_api_client = twitch_api_client
        self._polling_interval_minutes = polling_interval_minutes

        self._database = Database('database.json')
        self._database.load()

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
            time.sleep(self._polling_interval_minutes * 60)

    def _update(self):
        # Remove expired campaigns from database
        for key, value in list(self._database.get_campaigns()):
            end_date = get_datetime(value['endAt'])
            if end_date < datetime.datetime.now(datetime.timezone.utc):
                self._database.remove_campaign(key)

        # Get all drop campaigns
        logger.info('Fetching campaigns...')
        campaigns = self._twitch_api_client.get_drop_campaigns()
        logger.info(f'Found {len(campaigns)} campaigns.')

        # Update drop campaign database and find new campaigns
        new_campaigns = []
        new_games = []
        for campaign in campaigns:

            # Ignore campaigns that have already ended
            if datetime.datetime.now(datetime.timezone.utc) >= get_datetime(campaign['endAt']):
                continue

            # Get campaign details TODO: Requires integrity check
            # try:
            #     campaign = self._twitch_api_client.get_drop_campaign_details([campaign['id']])[0]
            # except Exception as e:
            #     logger.error('Error getting drop campaign details!', exc_info=e)
            #     continue

            # Check for new campaigns
            if self._database.add_campaign(campaign):
                logger.info('New campaign: ' + campaign['game']['displayName'] + ' ' + campaign['name'])
                new_campaigns.append(campaign)

            # Check for new games
            game = campaign['game']
            if self._database.add_game(game):
                logger.info('New game: ' + game['displayName'])
                new_games.append(game)

        # Notify listeners
        if len(new_campaigns) > 0:
            _call_all(self._on_new_campaigns_listeners, list(new_campaigns))
        if len(new_games) > 0:
            _call_all(self._on_new_games_listeners, list(new_games))

        # Save database
        self._database.save()

    def add_on_new_campaigns_listener(self, listener):
        self._on_new_campaigns_listeners.append(listener)

    def add_on_new_games_listener(self, listener):
        self._on_new_games_listeners.append(listener)
