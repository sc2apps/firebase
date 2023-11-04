import asyncio
import os
from datetime import datetime, timedelta

from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore import Client as FSClient
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.collection import CollectionReference
from utils import MATCHES_COLLECTION, PLAYERS_COLLECTION

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(cred)
db: FSClient = firestore.client()


def migrate_player_region():
    playersCol: CollectionReference = db.collection(PLAYERS_COLLECTION)

    players: list[DocumentSnapshot] = playersCol.get()

    for player in players:
        data = player.to_dict()

        if not data.get('regionId'):
            player.reference.set({
                'regionId': data['members'][0]['regionId']
            }, merge=True)


migrate_player_region()


def migrate_match_map_type():

    matchesCol: CollectionReference = db.collection(MATCHES_COLLECTION)

    matches: list[DocumentSnapshot] = matchesCol.get()

    for match in matches:
        data = match.to_dict()

        if not data.get('mapVariantMode'):
            match.reference.set({
                'mapVariantMode': '1V1',
            }, merge=True)


def migrate_player_mode():
    playersCol: CollectionReference = db.collection(PLAYERS_COLLECTION)

    players: list[DocumentSnapshot] = playersCol.get()

    for player in players:
        data = player.to_dict()

        if not data.get('mode'):
            player.reference.set({
                'mode': '1V1',
            }, merge=True)


# migrate_player_mode()
# migrate_player_region()
