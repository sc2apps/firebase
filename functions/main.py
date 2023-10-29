# The Firebase Admin SDK to delete users.
import asyncio
from datetime import datetime, timedelta

import google.cloud.firestore
import httpx
from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, scheduler_fn
from google.cloud.firestore_v1.base_query import FieldFilter
from utils import get_or_create_teams, handle_match

app = initialize_app()

MOD_IDS = [296214, 340252, 207314]

REQUEST_LIMIT = 80
REQUEST_WINDOW = 40  # seconds

request_count = 0
window_start_time = datetime.utcnow()


async def fetch_lobbies_for_region(region, checkUntil):
    global request_count, window_start_time
    lobbies = []
    after = ''

    async with httpx.AsyncClient() as client:
        while True:
            # If we've made 100 requests, wait for the remainder of the 40 seconds
            if request_count >= REQUEST_LIMIT:
                elapsed_time = (datetime.utcnow() - window_start_time).seconds
                if elapsed_time < REQUEST_WINDOW:
                    await asyncio.sleep(REQUEST_WINDOW - elapsed_time)
                request_count = 0
                window_start_time = datetime.utcnow()

            url = f"https://sc2arcade.com/api/lobbies/history?regionId={region}&includeMatchResult=true&includeMatchPlayers=true&includeMapInfo=true&includeSlots=true&includeSlotsProfile=true&after={after}"
            # print(f'Loading url: {url} request count {request_count}')
            start_time = datetime.now()
            try:
                response = await client.get(url, timeout=5)
            except Exception as exc:
                delta = datetime.now() - start_time
                print(
                    f"Failed to load url after {delta.seconds} seconds:\n{url}\n{exc}")
                continue
            request_count += 1

            responseJson = response.json()

            results = responseJson['results']
            lastResult = results[len(results) - 1]

            lastCreated = lastResult['createdAt']
            lastCreated = datetime.fromisoformat(lastCreated[0:-1])

            for data in responseJson['results']:
                if data['extModBnetId'] in MOD_IDS and data['status'] == 'started':
                    lobbies.append(data)

            # print(f'Last created: {lastCreated}')
            if lastCreated < checkUntil:
                break

            after = responseJson['page']['next']

    return lobbies


async def get_lobbies():
    checkUntil = datetime.utcnow() - timedelta(hours=1)
    print('Checking until: ' + checkUntil.strftime('%Y-%m-%d %H:%M:%S'))

    regions = [1, 2, 3]

    # Get lobbies for all regions in parallel
    all_lobbies = await asyncio.gather(*(fetch_lobbies_for_region(region, checkUntil) for region in regions))

    # Flatten the list of lobbies
    lobbies = [lobby for region_lobbies in all_lobbies for lobby in region_lobbies]

    lobbies.sort(key=lambda x: (
        x['match'] and x['match']['completedAt']) or '')

    return lobbies

# @scheduler_fn.on_schedule(schedule="0 0 29 2 1", timeout_sec=300)


def update_match_participants(req):
    db: google.cloud.firestore.Client = firestore.client()
    matches = db.collection('matches').get()

    for match in matches:
        matchData = match.to_dict()
        teams = get_or_create_teams(db, matchData)
        print([t['identifier'] for t in teams])
        # continue

        match.reference.set({
            'participants': [t['identifier'] for t in teams],
        }, merge=True)


# @scheduler_fn.on_schedule(schedule="0 0 29 2 1", timeout_sec=300)
def update_player_dates(req):
    db: google.cloud.firestore.Client = firestore.client()
    players = db.collection('players').get()

    for player in players:
        playerData = player.to_dict()

        saveData = {}
        hasLastMatch = 'lastMatchAt' in playerData
        hasCreatedAt = 'createdAt' in playerData
        if hasLastMatch and hasCreatedAt:
            continue

        matches = db.collection('matches').where(
            filter=FieldFilter(
                'participants', 'array_contains', playerData['identifier'])
        ).get()

        matches.sort(key=lambda m: m.to_dict()['createdAt'])

        if not hasLastMatch:
            saveData['lastMatchAt'] = matches[-1].to_dict()['createdAt']
        if not hasCreatedAt:
            saveData['createdAt'] = matches[0].to_dict()['createdAt']

        # print(f'Player {playerData["identifier"]} would need {saveData}')
        player.reference.set(saveData, merge=True)


@scheduler_fn.on_schedule(schedule="*/5 * * * *", timeout_sec=300, min_instances=0, max_instances=1, concurrency=1, cpu=0.5, preserve_external_changes=True)
def check_lobbies(event: scheduler_fn.ScheduledEvent) -> None:
    recent_lobbies = asyncio.run(get_lobbies())
    print(f'Found lobbies {len(recent_lobbies)}')

    db: google.cloud.firestore.Client = firestore.client()

    for match in recent_lobbies:
        if not match.get('match') or not match['match'].get('completedAt'):
            continue

        match_ref = db.collection('matches') \
            .document(str(match["bnetRecordId"]))

        doc = match_ref.get()
        # match_ref.set(match)

        if not doc.exists:
            print('New match discovered')
            handle_match(db, match_ref, match)

    print("Done processing lobbies")

# TODO:
# Support uploading of replays
# Determine if a match already exists by players and rough time
# Ensure the replay had the mod
# Adjust player MMR


# @https_fn.on_call()
# def get_challenges(req: https_fn.CallableRequest) -> any:
#     db: google.cloud.firestore.Client = firestore.client()


# @https_fn.on_call()
# def migrate(req: https_fn.CallableRequest) -> any:
#     db: google.cloud.firestore.Client = firestore.client()
#     players = db.collection("players").get()

#     for player in players:
#         data = player.data()
#         if not data['regionId']:
#             player.set({
#                 'regionId': data['members']['regionId']
#             }, merge=True)

#     # req
