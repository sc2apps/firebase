import json
import os
import pprint
import re

import sc2reader

pp = pprint.PrettyPrinter(indent=2, )

replay_filename = 'replays/Blackburn LE (7).SC2Replay'

replay = sc2reader.load_replay(replay_filename, load_level=2)

pp.pprint(replay)
# replay.players
#
profileMatches = []
for player in replay.players:
    profileMatches.append({
        'decision': player.result.lower(),
        'profile': {
            # Would have to pull from someone
            # 'avatar': ''
            'profileId': player.toon_id or player.uid,
            'name': player.name,
            # 'realmId':
            'regionId': player.region_id,
        }
    })

# Get mapname from filename

match = {
    'createdAt': replay.start_time,
    # closedAt
    # replay.length exists if we need it

    # lostElo, wonElo
    # map
    # mapBnetId
    'map': replay.map_name,
    'match': {
        'completedAt': replay.end_time,
        'profileMatches': profileMatches
    }
}
