# The Firebase Admin SDK to delete users.
import asyncio
from datetime import datetime, timedelta

import google.cloud.firestore
import httpx
from arcade_api import get_lobbies
from firebase_admin import firestore, initialize_app
from firebase_functions import scheduler_fn
from utils import (MOD_IDS, REQUEST_LIMIT, REQUEST_WINDOW, get_or_create_teams,
                   handle_match, mod_document, mod_name, store_lobbies)

app = initialize_app()

# @scheduler_fn.on_schedule(schedule="0 0 29 2 1", timeout_sec=300)


# def update_match_participants(req):
# db: google.cloud.firestore.Client = firestore.client()
# matches = db.collection(MATCHES_COLLECTION).get()

# for match in matches:
#     matchData = match.to_dict()
#     teams = get_or_create_teams(db, matchData)
#     if not teams:
#         continue

#     print([t['identifier'] for t in teams])
#     # continue

#     match.reference.set({
#         'participants': [t['identifier'] for t in teams],
#     }, merge=True)

# @scheduler_fn.on_schedule(schedule="0 0 29 2 1", timeout_sec=300)
# def update_player_dates(req):
#     db: google.cloud.firestore.Client = firestore.client()
#     players = db.collection(PLAYERS_COLLECTION).get()

#     for player in players:
#         playerData = player.to_dict()

#         saveData = {}
#         hasLastMatch = 'lastMatchAt' in playerData
#         hasCreatedAt = 'createdAt' in playerData
#         if hasLastMatch and hasCreatedAt:
#             continue

#         matches = db.collection(MATCHES_COLLECTION).where(
#             filter=FieldFilter(
#                 'participants', 'array_contains', playerData['identifier'])
#         ).get()

#         matches.sort(key=lambda m: m.to_dict()['createdAt'])

#         if not hasLastMatch:
#             saveData['lastMatchAt'] = matches[-1].to_dict()['createdAt']
#         if not hasCreatedAt:
#             saveData['createdAt'] = matches[0].to_dict()['createdAt']

#         # print(f'Player {playerData["identifier"]} would need {saveData}')
#         player.reference.set(saveData, merge=True)


@scheduler_fn.on_schedule(schedule="*/5 * * * *", timeout_sec=300, min_instances=0, max_instances=1, concurrency=1, cpu=0.5, preserve_external_changes=True)
def check_lobbies(event: scheduler_fn.ScheduledEvent) -> None:
    recent_lobbies = asyncio.run(get_lobbies())
    print(f'Found lobbies {len(recent_lobbies)}')

    db = firestore.client()

    store_lobbies(db, recent_lobbies)
    print("Done processing lobbies")

# TODO:
# Support uploading of replays
# Determine if a match already exists by players and rough time
# Ensure the replay had the mod
# Adjust player MMR


# @https_fn.on_call()
# def get_challenges(req: https_fn.CallableRequest) -> any:
#     db: google.cloud.firestore.Client = firestore.client()
