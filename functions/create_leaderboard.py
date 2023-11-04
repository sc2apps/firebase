import os
from datetime import datetime, timedelta

from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from utils import PLAYERS_COLLECTION

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(cred)
db = firestore.client()

start = datetime(2023, 10, 1)
iso_this_month = start.isoformat()

# Assuming your players collection is named 'players', adjust if otherwise
players_collection = db.collection(PLAYERS_COLLECTION)
print(PLAYERS_COLLECTION)

# Replace 'your_region_value' with the appropriate region value you wish to filter by
region = 1

# Fetch players based on conditions provided
query = players_collection.where(
    filter=FieldFilter('lastMatchAt', '>=', iso_this_month))

players_query = query.where(filter=FieldFilter('regionId', '==', region))
print(players_query.count().get())
players_docs = players_query.stream()


# Convert the players' documents to a list and sort them by 'elo' in descending order
players = sorted([doc.to_dict() for doc in players_docs],
                 key=lambda x: x['elo'], reverse=True)

# Add these sorted players to the /leaderboards/2023-10 collection (or document)
leaderboard_ref = db.collection('leaderboards').document('2023-10')
leaderboard_ref.set({
    'players': players
})

print("Leaderboard for October 2023 has been set!")
