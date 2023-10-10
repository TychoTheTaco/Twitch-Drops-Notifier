import json

from google.cloud import firestore

if __name__ == '__main__':

    firestore_client = firestore.Client()

    data = []
    for game_document in firestore_client.collection('campaign_details').list_documents():
        data.append(game_document.get().to_dict())

    # Write to file
    with open('data.json', 'w') as file:
        json.dump(data, file)
