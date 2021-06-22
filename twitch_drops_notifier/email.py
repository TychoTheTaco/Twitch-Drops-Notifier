import base64
import datetime
import urllib.parse
import logging
from email.mime.text import MIMEText

import pytz
from googleapiclient.discovery import build
from google.cloud import firestore


# Set up logging
logger = logging.getLogger(__name__)


def get_datetime(timestamp):
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")


def format_campaigns_list(user, campaigns):
    text = ''
    for campaign in sorted(campaigns, key=lambda x: get_datetime(x['endAt'])):
        start_time = get_datetime(campaign['startAt'])
        end_time = get_datetime(campaign['endAt'])

        # Convert start and end times to user-specified timezone
        if 'timezone' in user:
            try:
                start_time_local = start_time.astimezone(pytz.timezone(user['timezone']))
                end_time_local = end_time.astimezone(pytz.timezone(user['timezone']))
                start_time = start_time_local
                end_time = end_time_local
            except pytz.exceptions.UnknownTimeZoneError:
                pass

        text += f'<b>{campaign["game"]["displayName"]}</b><br>'
        text += 'Starts: ' + start_time.strftime('%d %B %Y %H:%M %Z') + '<br>'
        text += 'Ends  : ' + end_time.strftime('%d %B %Y %H:%M %Z') + '<br>'
        text += f'<a href="https://www.twitch.tv/directory/game/{urllib.parse.quote(campaign["game"]["displayName"])}?tl=c2542d6d-cd10-4532-919b-3d19f30a768b">Watch now!</a>'
        text += '<br><br>'
    return text


class EmailSender:

    def __init__(self, credentials):
        self._gmail_service = build('gmail', 'v1', credentials=credentials)
        self._firestore_client = firestore.Client()

    def on_new_campaigns(self, campaigns: []):
        logger.info('Sending out emails...')

        # Notify users of new campaigns
        for user in self._firestore_client.collection('users').stream():
            user = user.to_dict()
            pending_campaigns = []
            for campaign in campaigns:
                if len(user['games']) == 0 or campaign['game']['id'] in user['games']:
                    pending_campaigns.append(campaign)

            if len(pending_campaigns) > 0:
                logger.info('Sending new campaigns email to: ' + str(user))
                try:
                    self._send_new_campaigns_email(user, pending_campaigns)
                except Exception as e:
                    logger.error('Failed to send email: ' + str(e))

    def _create_edit_and_unsubscribe_footer(self, user):
        domain = 'https://twitch-drops-bot.uw.r.appspot.com/'
        content = f'<a href="{domain}/edit?id={user["id"]}">Edit Preferences</a> | <a href="{domain}/unsubscribe?id={user["id"]}">Unsubscribe</a>'

        content += '<style></style>'
        return content

    def _send(self, to, subject, body):
        message = MIMEText(body, 'html')
        message['to'] = to
        message['from'] = 'twitchdropsbot@gmail.com'
        message['subject'] = subject
        message = {'raw': base64.urlsafe_b64encode(message.as_string().encode('utf-8')).decode('utf-8')}

        self._gmail_service.users().messages().send(userId='me', body=message).execute()

    def _send_new_campaigns_email(self, user, campaigns):
        body = 'Here is a list of new Twitch Drop campaigns:<br><br>'
        body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'New Twitch Drop Campaigns!', body)

    def send_initial_email(self, user, campaigns):
        body = 'Here is a list of currently active Twitch drop campaigns:<br><br>'
        body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)

    def send_update_email(self, user, campaigns):
        body = 'You recently updated your preferences. Here is an updated list of active drop campaigns.<br><br>'
        body += format_campaigns_list(user, campaigns)
        body += self._create_edit_and_unsubscribe_footer(user)
        self._send(user['email'], 'Active Twitch Drop Campaigns', body)
