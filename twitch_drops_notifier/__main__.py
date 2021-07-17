import datetime
import json
import logging
import argparse

from google.cloud import firestore

from .twitch_drops_watchdog import TwitchDropsWatchdog
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


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


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
    parser.add_argument('--google-credentials',
                        help='The path to the credentials for Google',
                        dest='google_credentials',
                        default='google.json')
    parser.add_argument('--sleep-delay',
                        help='The number of seconds to wait in between requests for new drop campaigns.',
                        dest='sleep_delay',
                        default=60 * 60 * 1,
                        type=int)
    args = parser.parse_args()

    # Load Twitch credentials
    with open(args.twitch_credentials, 'r') as file:
        twitch_credentials = json.load(file)

    firestore_client = firestore.Client()

    # Create watchdog
    watchdog = TwitchDropsWatchdog(twitch_credentials, firestore_client, sleep_delay_seconds=args.sleep_delay)

    # Create email sender
    email_sender = EmailSender(args.gmail_credentials, args.google_credentials, firestore_client, watchdog)

    # Start watchdog
    watchdog.start()
