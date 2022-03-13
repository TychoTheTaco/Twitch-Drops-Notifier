import json
import logging
import argparse

from .twitch import Client
from .twitch_drops_watchdog import TwitchDropsWatchdog
from .notifiers.notifier import Notifier
from .notifiers.email_notifier import EmailNotifier, JSONEmailRecipientLoader


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
logging.basicConfig(format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s', level=logging.DEBUG, datefmt='%m/%d/%Y %H:%M:%S')
logging.getLogger().handlers[0].addFilter(logging_filter)


def load_notifiers(config) -> [Notifier]:
    notifiers_json = config['notifiers']

    notifiers = []

    # Create email notifier
    email_notifier_json = notifiers_json.get('email')
    if email_notifier_json is not None:

        # Load recipients
        email_recipients_json = email_notifier_json.get('recipients')
        if email_recipients_json is not None:
            email_recipient_loader = JSONEmailRecipientLoader(email_recipients_json)

            # Load email credentials
            email_credentials = email_notifier_json.get('credentials')
            if email_credentials is None:
                logger.error('No email credentials provided!')
                exit(1)

            # Create notifier
            notifiers.append(EmailNotifier(email_credentials, email_recipient_loader))
        else:
            logger.warning('No recipients specified for email notifier!')

    return notifiers


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
    twitch_api_client = Client(twitch_credentials['client_id'], twitch_credentials['oauth_token'], twitch_credentials['channel_login'])

    # Create watchdog
    watchdog = TwitchDropsWatchdog(twitch_api_client, polling_interval_minutes=args.polling_interval)

    # Load config
    with open('config.json', 'r') as file:
        config = json.load(file)

    # Load notifiers
    notifiers = load_notifiers(config)

    # Add notifiers
    def on_new_games(*args):
        for notifier in notifiers:
            notifier.on_new_games(*args)
    def on_new_campaigns(*args):
        for notifier in notifiers:
            notifier.on_new_drop_campaigns(*args)
    watchdog.add_on_new_games_listener(on_new_games)
    watchdog.add_on_new_campaigns_listener(on_new_campaigns)

    # Start watchdog
    watchdog.start()


if __name__ == '__main__':
    main()
