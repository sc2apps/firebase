import os
from datetime import timedelta

from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from utils import handle_match

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(cred)
db = firestore.client()


# Directory containing the SC2 replay files
replays_directory = 'replays/'

# List all files in the directory
replay_files = sorted(
    [f for f in os.listdir(replays_directory) if f.endswith('.SC2Replay')],
    key=lambda f: os.path.getmtime(os.path.join(replays_directory, f))
)


def to_datestr(date):
    return date.isoformat()[0:23]+'Z'


for replay_filename in replay_files:
    replay_path = os.path.join(replays_directory, replay_filename)

    # Load the SC2 replay
    replay = sc2reader.load_replay(replay_path, load_level=2)
    profileMatches = []
    slots = []
    for idx, player in enumerate(replay.players):
        profile = {
            'profileId': player.toon_id or player.uid,
            'name': player.name,
            'regionId': player.region_id,
        }
        profileMatches.append({
            'decision': player.result.lower() if player.result else 'unknown',
            'race': player.play_race,
            'profile': profile
        })

        slots.append({
            'kind': 'human' if player.is_human else ('referee' if player.is_referee else ('observer' if player.is_observer else 'unknown')),
            'name': player.name,
            'slotNumber': idx,
            'team': player.team_id,
            'race': player.play_race,
            'profile': {
                'profileId': player.toon_id or player.uid,
                'name': player.name,
                'regionId': player.region_id,
            }
        })

    match = {
        'createdAt': to_datestr(replay.start_time),
        'map': {
            'name': replay.map_name,
        },
        'match': {
            'completedAt': to_datestr(replay.end_time),
            'profileMatches': profileMatches
        },
        'slots': slots
    }

    # Check if a similar match already exists within a time window
    similar_matches = db.collection('matches').where(
        filter=FieldFilter('createdAt', '>=',
                           to_datestr(replay.start_time - timedelta(minutes=2)),)
    ).where(
        filter=FieldFilter('createdAt', '<=',
                           to_datestr(replay.start_time + timedelta(minutes=1)),)
    ).stream()

    # Check if similar matches with the same players exist
    for existing_match in similar_matches:
        existing_data = existing_match.to_dict()
        existing_profiles = [pm['profile']['profileId']
                             for pm in existing_data['match']['profileMatches']]
        new_profiles = [pm['profile']['profileId']
                        for pm in match['match']['profileMatches']]

        if set(existing_profiles) == set(new_profiles):
            print('A similar match already exists. Skipping...')
            break
    else:
        handle_match(db, None, match)
