import time
from abc import abstractmethod
import datetime
import logging
from email.mime.text import MIMEText
import smtplib
from pathlib import Path
from typing import Optional, List, Iterator, Any

import pytz
import requests
from jinja2 import Environment, FileSystemLoader
from jinja2.filters import FILTERS

from .notifier import Notifier, Recipient, RecipientLoader, EventMapType, Subscriber
from ..twitch import Game, DropCampaign

# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def convert_time(value, timezone):
    try:
        # TODO: use provided timezone
        value = get_datetime(value).astimezone(datetime.datetime.now().astimezone().tzinfo)
    except pytz.exceptions.UnknownTimeZoneError:
        pass
    return value.strftime('%d %B %Y %H:%M %Z')


FILTERS['convert_time'] = convert_time


class DiscordSubscriber(Subscriber):

    def __init__(self, events: EventMapType, webhook_url: str):
        super().__init__(events)
        self._webhook_url = webhook_url

    def webhook_url(self) -> str:
        return self._webhook_url


class DiscordNotifier(Notifier):

    @staticmethod
    def _create_field(name: str, value: Any):
        return {
            'name': name,
            'value': value
        }

    def _post(self, url: str, data: Any):
        response = requests.post(url, json=data)
        # TODO: Lazy solution to avoid too many requests
        time.sleep(1)
        if 200 <= response.status_code < 300:
            return
        else:
            logger.error('Error sending post request: ' + str(response.status_code) + ' ' + response.text)

    def notify_on_new_drop_campaign(self, subscriber: DiscordSubscriber, campaign: DropCampaign):
        logger.info(f'Sending new_drop_campaign discord notification to {subscriber.webhook_url()}')
        timezone = datetime.datetime.now().astimezone().tzname()
        self._post(subscriber.webhook_url(), {
            'embeds': [
                {
                    'title': 'New Drop Campaign',
                    'fields': [
                        DiscordNotifier._create_field('Game', campaign['game']['displayName']),
                        DiscordNotifier._create_field('Campaign', campaign['name']),
                        DiscordNotifier._create_field('Starts', convert_time(campaign['startAt'], timezone)),
                        DiscordNotifier._create_field('Ends', convert_time(campaign['endAt'], timezone)),
                    ],
                    'thumbnail': {
                        'url': campaign['imageURL'] if campaign.get('imageURL') else campaign['game']['boxArtURL']
                    }
                }
            ]
        })

    def notify_on_new_game(self, subscriber: DiscordSubscriber, game: Game):
        logger.info(f'Sending new_game discord notification to {subscriber.webhook_url()}')
        self._post(subscriber.webhook_url(), {
            'embeds': [
                {
                    'title': 'New Game',
                    'fields': [
                        DiscordNotifier._create_field('Name', game['displayName'])
                    ],
                    'thumbnail': {
                        'url': game['boxArtURL']
                    }
                }
            ]
        })
