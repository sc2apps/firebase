import json
import os
import pprint
import re

import sc2reader

pp = pprint.PrettyPrinter(indent=2, )

replay_filename = 'replays/Cognite vs Quoror G1.SC2Replay'

replay = sc2reader.load_replay(replay_filename, load_level=2)

def recursive_print(obj, indent=0):
    # Base case for primitives
    if isinstance(obj, (int, float, str, bool, type(None))):
        print(' ' * indent + str(obj))
        return

    # If it's a dictionary, iterate through its sorted keys
    if isinstance(obj, dict):
        for key in sorted(obj):
            print(' ' * indent + str(key) + ':')
            recursive_print(obj[key], indent + 2)
    # If it's a list or a tuple, iterate through items
    elif isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            print(' ' * indent + f'[{index}]:')
            recursive_print(item, indent + 2)
    # If it's a set, iterate through sorted items
    elif isinstance(obj, set):
        for item in sorted(obj):
            recursive_print(item, indent + 2)
    # If it's an object, iterate through sorted attributes
    else:
        for attr in dir(obj):
            # Filter out private attributes
            if attr.startswith("__") and attr.endswith("__"):
                continue
            print(' ' * indent + str(attr) + ':')
            try:
                val = getattr(obj, attr)
                recursive_print(val, indent + 2)
            except Exception as e:
                print(' ' * indent + f'Error: {e}')

recursive_print(replay, indent=1)
# pp.pprint(replay)
# # replay.players
# #
# profileMatches = []
# for player in replay.players:
#     profileMatches.append({
#         'decision': player.result.lower(),
#         'profile': {
#             # Would have to pull from someone
#             # 'avatar': ''
#             'profileId': player.toon_id or player.uid,
#             'name': player.name,
#             # 'realmId':
#             'regionId': player.region_id,
#         }
#     })

# # Get mapname from filename

# match = {
#     'createdAt': replay.start_time,
#     # closedAt
#     # replay.length exists if we need it

#     # lostElo, wonElo
#     # map
#     # mapBnetId
#     'map': replay.map_name,
#     'match': {
#         'completedAt': replay.end_time,
#         'profileMatches': profileMatches
#     }
# }
