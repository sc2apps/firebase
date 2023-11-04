import datetime
# The Firebase Admin SDK to delete users.
from datetime import datetime, timedelta

import google.cloud.firestore
import pyelo
import requests
from firebase_admin import firestore, initialize_app
from firebase_functions import scheduler_fn
from google.cloud.firestore_v1.base_collection import DocumentSnapshot
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference

MOD_IDS = {
    "scion": {
        1: [296214, 340252],
        2: [207314, 239826],
        3: [122362, 153152],
    },
    "all_races": {
        1: [339136],
        2: [239035],
        3: [152312],
    }
}

REQUEST_LIMIT = 80
REQUEST_WINDOW = 40  # seconds

ELO_MEAN = 2500
ELO_K = 80
ELO_RPA = 800

REGION_COLLECTION = "regions"
RACES_COLLECTION = "races"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"

REGION_MAPPING = {
    "na": 1,
    "eu": 2,
    "kr": 3
}


def region_as_number(region):
    if isinstance(region, str):
        # Returns None if the region string is not recognized
        return REGION_MAPPING.get(region, None)
    return region


def mod_name(mod_id):
    mod = mod_id

    for mod in MOD_IDS:
        for region in mod:
            for imod_id in region:
                if imod_id == mod_id:
                    return mod

# The document that holds the players/matches/leaderboards collections mod


def mod_document(db, region, mod_name) -> DocumentReference:
    region_collection: CollectionReference = db.collection(REGION_COLLECTION)
    region_document: DocumentReference = region_collection.document(
        str(region_as_number(region)))
    race_collection: CollectionReference = region_document.collection(
        RACES_COLLECTION)
    race_document: DocumentReference = race_collection.document(mod_name)
    return race_document


def init_pyelo():
    pyelo.setMean(ELO_MEAN)
    pyelo.setK(ELO_K)
    pyelo.setRPA(ELO_RPA)


def get_or_create_teams(mod_document: DocumentReference, match):
    # Use the slots to get player profiles
    teamPlayers = {}
    mode = match['mapVariantMode']

    for slot in match['slots']:
        if not teamPlayers.get(slot['team']):
            teamPlayers[slot['team']] = []
        if not slot.get('profile'):
            return False

        teamPlayers[slot['team']].append(slot['profile'])

    teams = []

    for t in teamPlayers.keys():
        players = teamPlayers[t]
        players = [p for p in players if not p is None]

        # Generate team identifier
        team_id = generate_team_identifier(players, mode)
        team_name = generate_team_name(players)

        # Try to get the team from Firestore
        if not team_id:
            continue
        team_ref = mod_document.collection(PLAYERS_COLLECTION) \
            .document(team_id)
        doc = team_ref.get()
        teamData = {}

        if not doc.exists:
            # If team doesn't exist, create it
            teamData = {
                "mode": mode,
                "identifier": team_id,
                "name": team_name,
                "members": [player for player in players],
                "regionId": players[0]['regionId'],
                "realmId": players[0].get('realmId'),
                "numGames": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                # It occurs to me this is mega abusable.  Won't do.
                # "elo": ELO_MEAN * max(1, len(players) * 0.75) if mode == '1V1' else ELO_MEAN,
                "elo": ELO_MEAN,
                "upsets": 0,
                "beenUpset": 0,
                "createdAt": datetime.utcnow().isoformat()[0:23]+'Z',
            }
            print(f'Created team with ID: {team_id}')
            teams.append(teamData)
        else:
            print(f'Team with ID: {team_id} already exists.')
            teams.append(doc.to_dict())
    return teams


def generate_team_identifier(players, mode):
    # Extract profile IDs, sort them, and then join them into a string
    ids = [str(player["profileId"]) for player in players]
    ids.sort()
    mode = mode or '1V1'

    return "-".join(ids) + (mode if mode != '1V1' else '')


def generate_team_name(players):
    names = [str(player["name"]) for player in players]
    names.sort()
    return ", ".join(names)


def eloPlayerFor(team):
    player = pyelo.createPlayer(team['identifier'])
    for key in ['numGames', 'wins', 'losses', 'draws', 'elo', 'upsets', 'beenUpset']:
        setattr(player, key, team[key])
    return player


def applyEloStatsTo(player, team):
    for key in ['numGames', 'wins', 'losses', 'draws', 'elo', 'upsets', 'beenUpset']:
        team[key] = getattr(player, key)


# This feels abusable so I'm not doing it for now
def multipliers_for(player, opponent):
    playerNew = player.numGames < 5
    opponentNew = opponent.numGames < 5

    # We both don't have many games, just do 1
    if playerNew and opponentNew or not playerNew and not opponentNew:
        return (1, 1)
    # Opponent is "new",
    if opponentNew:
        return (0.5, 2)
    # Player is "new"
    if playerNew:
        return (2, 0.5)


def datetimeFromDBIso(date) -> datetime:
    datetime.fromisoformat(date[0:-1])

# Will be used to update leaderboards


# def persist_players(db, players):
#     leaderboardCol: CollectionReference = db.collection('leaderboards')
#     for i in players:
#         lastMatchAt = datetimeFromDBIso(player['lastMatchAt'])  # iso timestamp

#         year = lastMatchAt.year
#         quarterly = f'{year}-q{(lastMatchAt.month-1) // 3 + 1}'
#         monthly = f'{year}-{lastMatchAt.month}'

#         for term in [year, quarterly, monthly]:
#             # The tricky thing I'm considering is - if we can cache all players in one document (the leaderboard) without subcollections, then it's one "read" saving costs
#             # And we have long term persistence of their data at that time.
#             # The problem arises in that if we do that, we could have race cases where we query the record update it and persist it - if two things do that we loose data
#             # It may not be a huge problem since we only have one script/instance writing data.  Unless for example, I import replays at the same time..
#             # Firebase has ArrayUnion and ArrayRemove; however, I believe they work via the exact dictionary

#             termRef = leaderboardCol.document(term)
#             data = termRef.get().to_dict()

#             if player['numGames'] < 5:
#                 break
#                 yearBoard = leaderboardCol.document(year).get()
#                 quarterBoard = leaderboardCol.document('year').get()
#                 yearBoard = leaderboardCol.document('year').get()

#                 yearBoard.to_dict()['players']


def handle_match(db, match_ref, match):
    init_pyelo()

    mod = mod_name(match['extModBnetId'])

    mod_doc = mod_document(
        db, match['regionId'], mod
    )
    teams = get_or_create_teams(mod_doc, match)

    if not teams:
        print("Teams were invalid")
        return
    if len(teams) > 2:
        print('More than two teams')
        return
    if len(teams) < 2:
        print('Only one player team')
        return

    firstProfile = match['match']['profileMatches'][0]
    secondProfile = match['match']['profileMatches'][0]

    # IDk what is reported for ties.  Hopefully this catches it xD
    tie = (firstProfile['decision'] == 'loss' and firstProfile['decision'] == 'loss') or \
        (firstProfile['decision'] ==
         'tie' and firstProfile['decision'] == 'tie')

    firstTeamWon = str(
        firstProfile['profile']['profileId']) in teams[0]['identifier']
    if firstProfile['decision'] == 'loss':
        firstTeamWon = not firstTeamWon

    # TODO: Handle ties

    winningTeam = teams[0] if firstTeamWon else teams[1]
    loosingTeam = teams[1] if firstTeamWon else teams[0]

    print(f'{winningTeam["name"]} won against {loosingTeam["name"]}')

    winningEloTeam = eloPlayerFor(winningTeam)
    loosingEloTeam = eloPlayerFor(loosingTeam)

    wonElo = winningEloTeam.elo
    lostElo = loosingEloTeam.elo
    match['winnerMMR'] = winningEloTeam.elo
    match['looserMMR'] = loosingEloTeam.elo

    muls = multipliers_for(winningEloTeam, loosingEloTeam)

    pyelo.addGameResults(
        winningEloTeam, 0.5 if tie else 1, loosingEloTeam, 0.5 if tie else 0, 0, 0, 0,
        muls[0], muls[1]
    )

    wonElo = winningEloTeam.elo - wonElo
    lostElo = loosingEloTeam.elo - lostElo
    match['wonElo'] = wonElo
    match['lostElo'] = lostElo
    match['participants'] = [
        winningTeam['identifier'],
        loosingTeam['identifier'],
    ]
    if match_ref:
        match_ref.set(match)
    else:
        match_ref = mod_doc.collection(MATCHES_COLLECTION).add(match)

    applyEloStatsTo(winningEloTeam, winningTeam)
    applyEloStatsTo(loosingEloTeam, loosingTeam)

    print(
        f"Saving Players new elos: {winningTeam['name']}-{winningTeam['elo']} and {loosingTeam['name']}-{loosingTeam['elo']}")
    playersCol = mod_doc.collection(PLAYERS_COLLECTION)

    # TODO: handle monthly, quarterly, yearly
    leaderboard_ref = mod_doc.collection('leaderboards').document('2023-10')
    # leaderboard_ref.set({
    #     'players': players
    # })

    winningTeam['lastMatchAt'] = match['createdAt']
    loosingTeam['lastMatchAt'] = match['createdAt']
    playersCol.document(winningTeam['identifier']).set(winningTeam)
    playersCol.document(loosingTeam['identifier']).set(loosingTeam)


def store_lobbies(db: google.cloud.firestore.Client, lobbies):
    for match in lobbies:
        if not match.get('match') or not match['match'].get('completedAt'):
            continue

        match_ref: DocumentReference = db.collection(MATCHES_COLLECTION) \
            .document(str(match["bnetRecordId"]))
        mod_match_ref: DocumentReference = mod_document(
            db, match['regionId'], mod_name(match['extModBnetId']),
        ).collection(MATCHES_COLLECTION) \
            .document(str(match["bnetRecordId"]))

        match_ref.set(match)

        # Save mod match (with MMR/etc)
        doc: DocumentSnapshot = mod_match_ref.get()
        if not doc.exists:
            print('New match discovered')
            handle_match(db, mod_match_ref, match)
