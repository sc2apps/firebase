import asyncio
# The Firebase Admin SDK to delete users.
from datetime import datetime, timedelta

import google.cloud.firestore
from arcade_api import fetch_lobbies_for_region_mod
from firebase_admin import firestore, initialize_app
from firebase_functions import scheduler_fn
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from utils import (LEADERBOARDS_COLLECTION, MATCHES_COLLECTION, MOD_IDS,
                   PLAYERS_COLLECTION, handle_match, mod_document, mod_name)


async def process_matches_for_region_mod(db, region, mod_ids, checkUntil, onlyInTimeWindow=True):
    tasks = [
        fetch_lobbies_for_region_mod(region, mod_id, checkUntil)
        for mod_id in mod_ids
    ]

    all_results = await asyncio.gather(*tasks)
    lobbies = [lobby for id_lobbies in all_results for lobby in id_lobbies if lobby['match'] and lobby['match']['completedAt'] and lobby['match']['completedAt'][0:-1] > checkUntil.isoformat()]
    print(f"In region: {region} Mod{mod_ids} using {len(lobbies)} of {sum([len(r) for r in all_results])}")
    del all_results

    lobbies.sort(key=lambda x: x['match']['completedAt'])
    print(f"Region: {region} Mod{mod_ids} sorted ascending")

    prior_intervals = [None, None, None]
    prior_dates = []
    intervals = []
    dates = []
    leaderboard_needs_update = False

    for match in lobbies:
        # Store raw data in global list of matches
        match_ref: DocumentReference = db.collection(MATCHES_COLLECTION) \
            .document(str(match["bnetRecordId"]))
        match_ref.set(match)
        
        # Process specific match
        mod_doc = mod_document(
            db, match['regionId'], mod_name(match['extModBnetId']),
        )
        mod_match_ref: DocumentReference = mod_doc.collection(MATCHES_COLLECTION) \
            .document(str(match["bnetRecordId"]))

        # Save mod match (with MMR/etc)
        doc = mod_match_ref.get()
        if not doc.exists or not doc.to_dict()['wonElo']:
            print(f'{"Unprocessed" if doc.exists else "New"} match discovered')

            leaderboard_needs_update = True
            completed = datetime.fromisoformat(match['match']['completedAt'][0:-1])
            
            # Update leaderboards if this record moves onto the next month (before updating the player)
            quarterNumber = (completed.month -1) // 3 + 1
            intervals = [
                f"{completed.year}-{completed.month}",
                f"{completed.year}-q{quarterNumber}",
                f"{completed.year}"
            ]
            dates = [
                datetime(completed.year, completed.month, 1),
                datetime(completed.year, (quarterNumber - 1) * 3 + 1, 1),
                datetime(completed.year, 1, 1),
            ]
            if prior_intervals != intervals:
                if prior_intervals[0] is not None:
                    print("Got a change")
                    leaderboard_needs_update = False

                    for i in range(0, len(intervals)):
                        if prior_intervals[i] == intervals[i]:
                            break
                        update_leaderboard(region, mod_doc, prior_intervals[i], prior_dates[i])

                prior_intervals = intervals
                prior_dates = dates
            
            handle_match(db, mod_match_ref, match)

    if leaderboard_needs_update:
        for i in range(0, len(intervals)):
            update_leaderboard(region, mod_doc, intervals[i], dates[i])
        
# def update_leaderboard(region, mod_doc, leaderboard_name, start_date):
#     query = mod_doc.collection(PLAYERS_COLLECTION).where(
#         filter=FieldFilter('lastMatchAt', '>=', start_date.isoformat()+'Z'),
#     )
#     players_docs = list(query.stream())
#     print(f"Updating leaderboard {leaderboard_name} with {len(players_docs)} players")
#     players = sorted([doc.to_dict() for doc in players_docs],
#         key=lambda x: x['elo'], reverse=True)
    
#     mod_doc.collection(LEADERBOARDS_COLLECTION).document(leaderboard_name).set(
#         {
#             'players': players,
#             'regionId': region,
#         }
#     )

def update_leaderboard(region, mod_doc, leaderboard_name, start_date):
    # Get the current players from the leaderboard
    leaderboard_ref = mod_doc.collection(LEADERBOARDS_COLLECTION).document(leaderboard_name)
    current_leaderboard = leaderboard_ref.get().to_dict() or {}
    current_players = current_leaderboard.get('players', [])

    # Find the most recent match date among the current players
    most_recent_match = max([player['lastMatchAt'] for player in current_players], default=start_date.isoformat()+'Z')

    if most_recent_match < start_date.isoformat()+'Z':
        return

    # Query for players who have had a match more recently than the most recent match date
    query = mod_doc.collection(PLAYERS_COLLECTION).where(
        filter=FieldFilter('lastMatchAt', '>=', most_recent_match),
    )
    new_players_docs = list(query.stream())

    # Merge and sort the players
    new_players = [doc.to_dict() for doc in new_players_docs]
    all_players = current_players + new_players
    unique_players = {player['identifier']: player for player in all_players}.values()  # Removes duplicates
    sorted_players = sorted(unique_players, key=lambda x: x['elo'], reverse=True)

    print(f"Updating leaderboard {leaderboard_name} with {len(sorted_players)} players")

    # Update the leaderboard
    leaderboard_ref.set(
        {
            'players': sorted_players,
            'regionId': region,
        }
    )


async def process_matches(checkUntil=None, onlyInTimeWindow=True):
    db = firestore.client()
    checkUntil = checkUntil or datetime.utcnow() - timedelta(hours=2)
    print('Checking until: ' + checkUntil.strftime('%Y-%m-%d %H:%M:%S'))

    # Use list comprehension to create tasks for all regions and mods

    tasks = [
        process_matches_for_region_mod(db, region, mod_ids, checkUntil)
        for race, regions in MOD_IDS.items()
        for region, mod_ids in regions.items()
    ]

    all_results = await asyncio.gather(*tasks)
    print("All regions processed")
