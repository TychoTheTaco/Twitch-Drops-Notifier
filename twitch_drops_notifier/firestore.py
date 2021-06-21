import logging


from google.cloud import firestore


# Set up logging
logger = logging.getLogger(__name__)


class FirestoreUpdater:

    def __init__(self):
        self._firestore_client = firestore.Client()

    def on_new_campaigns(self, campaigns: []):

        # Update campaign database
        logger.info('Updating campaign database...')
        for campaign in campaigns:
            document = self._firestore_client.collection('campaigns').document(campaign['id'])
            if not document.get().exists:
                document.set(campaign)

        # Update game database
        logger.info('Updating game database...')
        for campaign in campaigns:
            game = campaign['game']
            self._firestore_client.collection('games').document(game['id']).set(game)
