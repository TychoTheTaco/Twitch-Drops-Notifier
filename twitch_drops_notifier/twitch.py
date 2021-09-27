import requests
import json
import time


def get_drop_campaigns(credentials: {str, str}):
    response = requests.post(
        'https://gql.twitch.tv/gql',
        headers={
            'Content-Type': 'text/plain;charset=UTF-8',
            'Client-Id': credentials['client_id'],
            'Authorization': f'OAuth {credentials["oauth_token"]}'
        },
        data=json.dumps([{
            'operationName': 'ViewerDropsDashboard',
            'extensions': {
                'persistedQuery': {
                    "version": 1,
                    "sha256Hash": "e8b98b52bbd7ccd37d0b671ad0d47be5238caa5bea637d2a65776175b4a23a64"
                }
            }
        }])
    )
    try:
        c = response.json()[0]['data']['currentUser']['dropCampaigns']
        return c
    except Exception as e:
        print(e)
        with open('dc-' + str(int(time.time())) + '.json', 'w') as file:
            file.write(response.json())
        return None


def get_drop_campaign_details(credentials: {str, str}, drop_ids):

    data = []
    for drop_id in drop_ids:
        data.append({
            'operationName': 'DropCampaignDetails',
            'extensions': {
                'persistedQuery': {
                    "version": 1,
                    "sha256Hash": "14b5e8a50777165cfc3971e1d93b4758613fe1c817d5542c398dce70b7a45c05"
                }
            },
            'variables': {
                'dropID': drop_id,
                'channelLogin': credentials['channel_login']
            }
        })

    response = requests.post(
        'https://gql.twitch.tv/gql',
        headers={
            'Content-Type': 'text/plain;charset=UTF-8',
            'Client-Id': credentials['client_id'],
            'Authorization': f'OAuth {credentials["oauth_token"]}'
        },
        data=json.dumps(data)
    )
    try:
        return [x['data']['user']['dropCampaign'] for x in response.json()]
    except Exception as e:
        print(e)
        with open('dcd-' + str(int(time.time())) + '.json', 'w') as file:
            file.write(response.json())
        return None
