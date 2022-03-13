import requests
import json


class Client:

    def __init__(self, client_id: str, oauth_token: str, channel_login: str):
        self._client_id = client_id
        self._oauth_token = oauth_token
        self._channel_login = channel_login

        self._api_root_url = 'https://gql.twitch.tv/gql'

        self._default_header = {
            'Content-Type': 'text/plain;charset=UTF-8',
            'Client-Id': client_id,
            'Authorization': f'OAuth {oauth_token}'
        }

    def _build_post_request(self, **kwargs):
        return requests.post(
            self._api_root_url,
            headers=self._default_header,
            **kwargs
        )

    def get_drop_campaigns(self):
        return self._build_post_request(data=json.dumps([{
            'operationName': 'ViewerDropsDashboard',
            'extensions': {
                'persistedQuery': {
                    "version": 1,
                    "sha256Hash": "e8b98b52bbd7ccd37d0b671ad0d47be5238caa5bea637d2a65776175b4a23a64"
                }
            }
        }])).json()[0]['data']['currentUser']['dropCampaigns']

    def get_drop_campaign_details(self, drop_campaign_ids: [str]):
        response = self._build_post_request(data=json.dumps([
            {
                'operationName': 'DropCampaignDetails',
                'extensions': {
                    'persistedQuery': {
                        "version": 1,
                        "sha256Hash": "14b5e8a50777165cfc3971e1d93b4758613fe1c817d5542c398dce70b7a45c05"
                    }
                },
                'variables': {
                    'dropID': drop_id,
                    'channelLogin': self._channel_login
                }
            }
            for drop_id in drop_campaign_ids
        ]))
        return [x['data']['user']['dropCampaign'] for x in response.json()]
