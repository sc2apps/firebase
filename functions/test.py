import json
import pprint

import sc2reader

pp = pprint.PrettyPrinter(indent=2)

replay = sc2reader.load_replay(
    'replays/Blackburn LE (7).SC2Replay', load_level=2)

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

match = {
    'createdAt': replay.start_time,
    # lostElo, wonElo
    # map
    # mapBnetId
    'match': {
        'completedAt': replay.end_time,
        'profileMatches': profileMatches
    }
}
