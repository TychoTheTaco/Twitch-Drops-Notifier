import time
from abc import abstractmethod, ABC
import datetime
import logging
from email.mime.text import MIMEText
import smtplib
from pathlib import Path
from typing import Optional, List, Iterator

import pytz
from jinja2 import Environment, FileSystemLoader
from jinja2.filters import FILTERS

from .notifier import EventMapType, BufferedNotifier, Subscriber, SubscriberIterator
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


class EmailSubscriberIterator(SubscriberIterator):

    @abstractmethod
    def __iter__(self) -> Iterator[EmailSubscriber]:
        raise NotImplementedError


class EmailNotifier(BufferedNotifier):

    def __init__(self, user: str, password: str, email_template_dir: str | Path):
        super().__init__()
        self._user = user
        self._password = password
        self._jinja_environment = Environment(loader=FileSystemLoader(Path(email_template_dir).resolve()))
        self._smtp_server = None

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
            logger.error('Failed to send email', exc_info=e)

    def send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = self._user
        message['subject'] = subject

        def create_smtp_server() -> smtplib.SMTP:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self._user, self._password)
            return server

        if self._smtp_server is None:
            self._smtp_server = create_smtp_server()

        try:
            self._smtp_server.send_message(message)
        except smtplib.SMTPServerDisconnected:
            logger.info('SMTP Server disconnected. Logging in again...')
            self._smtp_server = create_smtp_server()
            self._smtp_server.send_message(message)

        time.sleep(1.5)

    def _send_new_campaigns_email(self, recipient: EmailSubscriber, campaigns):
        logger.info('Sending new campaigns email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_campaigns.html').render(
            user={
                'timezone': recipient.timezone
            },
            campaigns=campaigns
        )
        self.send(recipient.email_address, 'New Twitch Drop Campaigns!', body)

    def _send_new_games_email(self, recipient: EmailSubscriber, games):
        logger.info('Sending new games email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_games.html').render(
            games=games
        )
        self.send(recipient.email_address, 'New Games', body)
