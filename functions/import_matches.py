import asyncio
import os
from datetime import datetime, timedelta

import httpx
from arcade_api import get_lobbies
from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from utils import MATCHES_COLLECTION, mod_document, mod_name, store_lobbies

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(
    cred
)
db = firestore.client()


def check_lobbies(checkUntil) -> None:
    recent_lobbies = asyncio.run(get_lobbies(checkUntil))
    print(f'Found lobbies {len(recent_lobbies)}')

    for match in recent_lobbies:
        if not match.get('match') or not match['match'].get('completedAt'):
            continue

        match_ref: DocumentReference = db.collection(MATCHES_COLLECTION) \
            .document(str(match["bnetRecordId"]))
        # mod_match_ref: DocumentReference = mod_document(
        #     db, match['regionId'], mod_name(match['extModBnetId']),
        # ).collection(MATCHES_COLLECTION) \
        #     .document(str(match["bnetRecordId"]))

        match_ref.set(match)
    print("Done processing lobbies")


checkUntil = datetime(2023, 1, 1, 0, 0, 0)
# checkUntil = datetime(2023, 10, 1, 0, 0, 0)
asyncio.run(check_lobbies(checkUntil))
