import json

import logging
import argparse

from .twitch_drops_watchdog import TwitchDropsWatchdog
from .firestore import FirestoreUpdater
from .email import EmailSender
from .utils import get_gmail_credentials


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


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--twitch-credentials',
                        help='The path to the credentials to use when interacting with the Twitch API.',
                        dest='twitch_credentials',
                        default='twitch.json')
    parser.add_argument('--gmail-credentials',
                        help='The path to the credentials for the Gmail account used to send email notifications.',
                        dest='gmail_credentials',
                        default='gmail.json')
    parser.add_argument('--sleep-delay',
                        help='The number of seconds to wait in between requests for new drop campaigns.',
                        dest='sleep_delay',
                        default=60 * 60 * 1,
                        type=int)
    args = parser.parse_args()

    # Load Twitch credentials
    with open(args.twitch_credentials, 'r') as file:
        twitch_credentials = json.load(file)

    # Get Gmail credentials and create service
    gmail_credentials = get_gmail_credentials('credentials/gmail.pickle', args.gmail_credentials)

    # Start bot
    bot = TwitchDropsWatchdog(twitch_credentials)
    bot.add_on_new_campaigns_listener(FirestoreUpdater().on_new_campaigns)
    bot.add_on_new_campaigns_listener(EmailSender(gmail_credentials).on_new_campaigns)
    bot.start()
