import json
import logging
import argparse
from typing import Any, Dict, TypeVar, Union, List, TypedDict

from twitch_drops_watchdog.notifiers.discord import DiscordNotifier, DiscordSubscriber
from .twitch import Client
from .twitch_drops_watchdog import TwitchDropsWatchdog
from .notifiers.notifier import Notifier, BufferedNotifier, EventMapType, NewDropCampaignEventOptions, Subscriber
from .notifiers.email import EmailNotifier, JSONEmailRecipientLoader, EmailSubscriber


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
logging.basicConfig(format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s', level=logging.DEBUG,
                    datefmt='%m/%d/%Y %H:%M:%S')
logging.getLogger().handlers[0].addFilter(logging_filter)


class ConfigurationParser:

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    def parse_notifiers(self) -> List[Notifier]:
        notifiers = []

        notifications_json = self._config.get('notifications')
        if not notifications_json:
            return notifiers

        # Discord
        discord_json = notifications_json.get('discord')
        if discord_json:

            subscribers_json = discord_json.get('subscribers')
            if subscribers_json:

                discord_notifier = DiscordNotifier()

                subscribers = []
                for subscriber_json in subscribers_json:

                    details = self._parse_common_subscriber_details(subscriber_json)

                    webhook_urls = subscriber_json.get('webhook_urls')
                    if not webhook_urls:
                        logger.error(f'Missing key "webhook_urls"')
                        continue

                    for webhook_url in webhook_urls:
                        discord_notifier.subscribe(DiscordSubscriber(details['events'], webhook_url))

                notifiers.append(discord_notifier)

        email_json = notifications_json.get('email')
        if email_json:

            credentials_json = email_json.get('credentials')
            if not credentials_json:
                logger.error('missing email credentials')
                return notifiers

            user = credentials_json.get('user')
            password = credentials_json.get('password')

            email_notifier = EmailNotifier(user, password)

            subscribers = self.parse_email_subscribers()
            for sub in subscribers:
                email_notifier.subscribe(sub)

            notifiers.append(email_notifier)

        return notifiers

    def parse_email_subscribers(self) -> List[EmailSubscriber]:

        notifications_json = self._config.get('notifications')
        if not notifications_json:
            return []

        email_json = notifications_json.get('email')
        if email_json:

            subscribers_json = email_json.get('subscribers')
            if subscribers_json:

                subscribers = []
                for subscriber_json in subscribers_json:

                    details = self._parse_common_subscriber_details(subscriber_json)

                    recipients = subscriber_json.get('recipients')
                    if not recipients:
                        logger.error(f'Missing key "recipients"')
                        continue

                    for recipient in recipients:
                        subscribers.append(EmailSubscriber(details['events'], recipient))

        return subscribers

    def _parse_common_subscriber_details(self, subscriber_json) -> Dict[str, Any]:
        events_json = subscriber_json.get('events')
        if not events_json:
            logger.error(f'Missing key "events_json"')
            return {}

        events: EventMapType = {}

        for key, value in events_json.items():

            if key == 'new_drop_campaign':

                games_json = value.get('games')
                if games_json:
                    events['new_drop_campaign'] = {'games': games_json}
                else:
                    events['new_drop_campaign'] = {'games': []}

            elif key == 'new_game':
                events['new_game'] = {}
            else:
                logger.error(f'Unrecognized event "{key}"')
                continue

        return {
            'events': events
        }


def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--twitch-credentials',
                        help='The path to the credentials to use when interacting with the Twitch API.',
                        dest='twitch_credentials',
                        default='twitch.json')
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

    # Create watchdog
    watchdog = TwitchDropsWatchdog(twitch_client, polling_interval_minutes=args.polling_interval)

    # Load config
    with open('config.json', 'r') as file:
        config = json.load(file)

    # Load notifiers
    configuration_parser = ConfigurationParser(config)
    notifiers = configuration_parser.parse_notifiers()

    # Add notifiers
    def on_new_games(games):
        for notifier in notifiers:
            for item in games:
                notifier.on_new_game(item)
            if isinstance(notifier, BufferedNotifier):
                notifier.send_all_events()

    def on_new_campaigns(campaigns):
        for notifier in notifiers:
            for item in campaigns:
                notifier.on_new_drop_campaign(item)
            if isinstance(notifier, BufferedNotifier):
                notifier.send_all_events()

    watchdog.add_on_new_games_listener(on_new_games)
    watchdog.add_on_new_campaigns_listener(on_new_campaigns)

    # Start watchdog
    watchdog.start()


if __name__ == '__main__':
    main()
