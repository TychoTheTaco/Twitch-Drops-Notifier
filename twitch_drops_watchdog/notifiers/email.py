from abc import abstractmethod
import datetime
import logging
from email.mime.text import MIMEText
import smtplib
from pathlib import Path
from typing import Optional, List, Iterator

import pytz
from jinja2 import Environment, FileSystemLoader
from jinja2.filters import FILTERS

from .notifier import Notifier, Recipient, RecipientLoader, EventMapType, BufferedNotifier, Subscriber
from ..twitch import Game, DropCampaign

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


class EmailRecipient(Recipient):

    def __init__(self, email_address: str, game_ids: Optional[List[str]] = None, new_game_notifications: bool = True, timezone: str = 'utc'):
        super().__init__(game_ids, new_game_notifications)
        self._email_address = email_address
        self._timezone = timezone

    @property
    def email_address(self):
        return self._email_address

    @property
    def timezone(self):
        return self._timezone


class EmailRecipientLoader(RecipientLoader):

    @abstractmethod
    def __iter__(self) -> Iterator[EmailRecipient]:
        raise NotImplementedError


class JSONEmailRecipientLoader(EmailRecipientLoader):
    """
    Load email recipients from a JSON file.
    """

    def __init__(self, json_data):
        self._recipients = []
        for item in json_data:
            self._recipients.append(EmailRecipient(
                item['email'],
                item['games'],
                item['new_game_notifications']
            ))

    def __iter__(self) -> Iterator[EmailRecipient]:
        for recipient in self._recipients:
            yield recipient


class EmailSubscriber(Subscriber):

    def __init__(self, events: EventMapType, email_address: str, timezone: str = 'utc'):
        super().__init__(events)
        self._email_address = email_address
        self._timezone = timezone

    @property
    def email_address(self):
        return self._email_address

    @property
    def timezone(self):
        return self._timezone


class EmailNotifier(BufferedNotifier):

    def __init__(self, user: str, password: str):
        super().__init__()
        self._user = user
        self._password = password
        self._jinja_environment = Environment(loader=FileSystemLoader(Path(__file__, '..', '..', 'email_templates').resolve()))

    def notify_on_new_drop_campaigns(self, subscriber: EmailSubscriber, campaigns: [DropCampaign]):
        # Send new campaigns email
        try:
            self._send_new_campaigns_email(subscriber, campaigns)
        except Exception as e:
            logger.error('Failed to send email!', exc_info=e)

    def notify_on_new_games(self, subscriber: EmailSubscriber, games: [Game]):
        try:
            self._send_new_games_email(subscriber, games)
        except Exception as e:
            logger.error('Failed to send email: ' + str(e))

    def _send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = self._user
        message['subject'] = subject

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(self._user, self._password)
        server.send_message(message)
        server.quit()

    def _send_new_campaigns_email(self, recipient: EmailSubscriber, campaigns):
        logger.info('Sending new campaigns email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_campaigns.html').render(
            user={
              'timezone': recipient.timezone
            },
            campaigns=campaigns
        )
        self._send(recipient.email_address, 'New Twitch Drop Campaigns!', body)

    def _send_new_games_email(self, recipient: EmailSubscriber, games):
        logger.info('Sending new games email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_games.html').render(
            games=games
        )
        self._send(recipient.email_address, 'New Games', body)
