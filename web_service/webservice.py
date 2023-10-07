import datetime
import json
import logging
import argparse

from google.cloud import firestore

from twitch_drops_watchdog import TwitchDropsWatchdog
from twitch_drops_watchdog.notifiers.email import EmailNotifier, FirestoreEmailRecipientLoader


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


def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--twitch-credentials',
                        help='The path to the credentials to use when interacting with the Twitch API.',
                        dest='twitch_credentials',
                        default='twitch.json')
    parser.add_argument('--email-credentials',
                        help='The path to the credentials for the email account used to send email notifications.',
                        dest='email_credentials',
                        default='email.json')
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

    firestore_client = firestore.Client()

    # Create watchdog
    watchdog = TwitchDropsWatchdog(twitch_credentials, polling_interval_minutes=args.polling_interval)

    # Create Firestore client
    firestore_client = firestore.Client()

    # Create email notifier
    email_recipient_loader = FirestoreEmailRecipientLoader(firestore_client)
    with open(args.email_credentials) as file:
        email_credentials = json.load(file)
    email_sender = EmailNotifier(email_credentials, email_recipient_loader)

    # Start watchdog
    watchdog.start()


if __name__ == '__main__':
    main()
