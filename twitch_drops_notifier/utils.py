import os
import pickle
import datetime

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def get_timestamp():
    return datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()


def get_gmail_credentials(pickle_path, credentials_path):
    credentials = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(pickle_path):
        with open(pickle_path, 'rb') as token:
            credentials = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, ['https://www.googleapis.com/auth/gmail.compose'])
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(pickle_path, 'wb') as token:
            pickle.dump(credentials, token)
    return credentials
