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

from .notifier import Notifier, Recipient, RecipientLoader


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
    Load email recipient data from a JSON file.
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


class EmailNotifier(Notifier):

    def __init__(self, credentials, recipient_loader: EmailRecipientLoader):
        self._credentials = credentials
        self._recipient_loader = recipient_loader

        self._jinja_environment = Environment(loader=FileSystemLoader(Path(__file__, '..', '..', 'email_templates').resolve()))

    def on_new_drop_campaigns(self, campaigns):
        for recipient in self._recipient_loader:

            # Get campaigns that the user is subscribed to
            subscribed_campaigns = []
            for campaign in campaigns:
                if len(recipient.game_ids) == 0 or campaign['game']['id'] in recipient.game_ids:
                    subscribed_campaigns.append(campaign)

            # Send new campaigns email
            if len(subscribed_campaigns) > 0:
                try:
                    self._send_new_campaigns_email(recipient, subscribed_campaigns)
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

    def on_new_games(self, games):
        for recipient in self._recipient_loader:
            if recipient.new_game_notifications:
                try:
                    self._send_new_games_email(recipient, games)
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

    def _send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = 'twitchdropsbot@gmail.com'
        message['subject'] = subject

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(self._credentials['user'], self._credentials['password'])
        server.send_message(message)
        server.quit()

    def _send_new_campaigns_email(self, recipient: EmailRecipient, campaigns):
        logger.info('Sending new campaigns email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_campaigns.html').render(
            user={
              'timezone': recipient.timezone
            },
            campaigns=campaigns
        )
        self._send(recipient.email_address, 'New Twitch Drop Campaigns!', body)

    def _send_new_games_email(self, recipient: EmailRecipient, games):
        logger.info('Sending new games email to: ' + recipient.email_address)
        body = self._jinja_environment.get_template('new_games.html').render(
            games=games
        )
        self._send(recipient.email_address, 'New Games', body)
