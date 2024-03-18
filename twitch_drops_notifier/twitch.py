import logging
import secrets
from typing import Optional, List

import requests
import json


# Set up logging
logger = logging.getLogger(__name__)


class Client:

    CLIENT_ID_TV = "ue6666qo983tsx6so1t0vnawi233wa"
    USER_AGENT_ANDROID_TV = "Mozilla/5.0 (Linux; Android 7.1; Smart Box C1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"

    def __init__(self, *, client_id: str, oath_token: Optional[str] = None, user_id: Optional[str] = None):
        self._client_id = client_id
        self._oauth_token = oath_token
        self._device_id = secrets.token_hex(32)
        self._client_session_id = secrets.token_hex(16)
        self._user_id = user_id

    def _post_authorized(self, data: str):
        assert self._oauth_token is not None, "Missing OAuth token!"

        response = requests.post(
            'https://gql.twitch.tv/gql',
            headers={
                'Authorization': f'OAuth {self._oauth_token}',
                #'Client-Id': self._client_id,
                #'Client-Version': 'fb9b8666-ae21-4697-a49b-69595ea176aa',
                #'Client-Session-Id': self._client_session_id,
                'Content-Type': 'text/plain;charset=UTF-8',
                #'User-Agent': Client.USER_AGENT_ANDROID_TV,
                #'X-Device-Id': self._device_id
            },
            data=data
        )

        if not response.ok:
            logger.error(f'Bad response: {response.status_code}')
            logger.debug(f'Request : {response.request.headers} {response.request.body}')
            logger.debug(f'Response: {response.text}')
            return None

        response_json = response.json()[0]

        errors = response_json.get('errors', None)
        if errors is not None:
            logger.error(f'Found errors in response!')
            logger.debug(errors)
            return None

        return response

    def get_drop_campaigns(self):
        response = self._post_authorized(json.dumps([{
            'operationName': 'ViewerDropsDashboard',
            'extensions': {
                'persistedQuery': {
                    "version": 1,
                    "sha256Hash": "e8b98b52bbd7ccd37d0b671ad0d47be5238caa5bea637d2a65776175b4a23a64"
                }
            }
        }]))

        if response is None:
            return None

        response_json = response.json()
        try:
            return response_json[0]['data']['currentUser']['dropCampaigns']
        except Exception as e:
            logger.exception('Bad response format!', exc_info=e)
            logger.debug(f'Request : {response.request.headers} {response.request.body}')
            logger.debug(f'Response: {response_json}')

        return None

    def get_drop_campaign_details(self, drop_campaign_ids: List[str]):
        data = []
        for drop_campaign_id in drop_campaign_ids:
            data.append({
                'operationName': 'DropCampaignDetails',
                'extensions': {
                    'persistedQuery': {
                        "version": 1,
                        "sha256Hash": "14b5e8a50777165cfc3971e1d93b4758613fe1c817d5542c398dce70b7a45c05"
                    }
                },
                'variables': {
                    'dropID': drop_campaign_id,
                    'channelLogin': self._user_id
                }
            })

        response = self._post_authorized(json.dumps(data))

        if response is None:
            return None

        response_json = response.json()

        try:
            return [x['data']['user']['dropCampaign'] for x in response_json]
        except Exception as e:
            logger.exception('Bad response format!', exc_info=e)
            logger.debug(f'Request : {response.request.headers} {response.request.body}')
            logger.debug(f'Response: {response_json}')

        return None
