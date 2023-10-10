import csv

from google.cloud import firestore

if __name__ == '__main__':

    firestore_client = firestore.Client()

    # Get sorted games list
    games = []
    for game_document in firestore_client.collection('games').list_documents():
        games.append(game_document.get().to_dict())
    games = list(sorted(games, key=lambda x: x['displayName']))

    # Write to file
    with open('games.csv', 'w', newline='\n') as file:
        csv_writer = csv.writer(file)
        for game in games:
            csv_writer.writerow((game['id'], game['displayName']))
