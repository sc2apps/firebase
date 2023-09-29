# The Firebase Admin SDK to delete users.
from datetime import datetime, timedelta

import google.cloud.firestore
import pyelo
import requests
from firebase_admin import firestore, initialize_app
from firebase_functions import scheduler_fn
from google.cloud.firestore_v1.base_query import FieldFilter

app = initialize_app()

ELO_MEAN = 2500
ELO_K = 80
ELO_RPA = 800

MOD_IDS = [296214, 340252]


def get_lobbies():
    checkUntil = datetime.utcnow() - timedelta(hours=2)
    print('Checking until: ' + checkUntil.strftime('%Y-%m-%d %H:%M:%S'))

    regions = [1, 2, 3, 5]

    # my match # &after=Wzg2MDI3NjMxXQ==

    lobbies = []

    for region in regions:
        after = ''
        # after = 'Wzg2MTgyMDMxXQ==' # ai games
        # after = 'Wzg2MDI3NjMxXQ==' # my original game
        while True:
            url = f"https://sc2arcade.com/api/lobbies/history?regionId={region}&includeMatchResult=true&includeMatchPlayers=true&includeMapInfo=true&includeSlots=true&includeSlotsProfile=true&after={after}"
            print(f'Loading url: {url}')
            response = requests.get(url)
            responseJson = response.json()

            results = responseJson['results']
            lastResult = results[len(results) - 1]

            lastCreated = lastResult['createdAt']
            lastCreated = datetime.fromisoformat(lastCreated[0:-1])

            for data in responseJson['results']:
                if data['extModBnetId'] in MOD_IDS and data['status'] == 'started':
                    lobbies.append(data)

            print(f'Last created: {lastCreated}')
            if lastCreated < checkUntil:
                break

            after = responseJson['page']['next']

    lobbies.sort(key=lambda x: (
        x['match'] and x['match']['completedAt']) or '')

    return lobbies


def generate_team_identifier(players):
    # Extract profile IDs, sort them, and then join them into a string
    ids = [str(player["profileId"]) for player in players]
    ids.sort()
    return "-".join(ids)


def generate_team_name(players):
    names = [str(player["name"]) for player in players]
    names.sort()
    return ", ".join(names)


def get_or_create_teams(db: google.cloud.firestore.Client, match):
    # Use the slots to get player profiles
    teamPlayers = {}

    for slot in match['slots']:
        if not teamPlayers.get(slot['team']):
            teamPlayers[slot['team']] = []
        teamPlayers[slot['team']].append(slot['profile'])

    teams = []

    for t in teamPlayers.keys():
        players = teamPlayers[t]
        players = [p for p in players if not p is None]

        # Generate team identifier
        team_id = generate_team_identifier(players)
        team_name = generate_team_name(players)

        # Try to get the team from Firestore
        if not team_id:
            continue
        team_ref = db.collection('players').document(team_id)
        doc = team_ref.get()
        teamData = {}

        if not doc.exists:
            # If team doesn't exist, create it
            teamData = {
                "identifier": team_id,
                "name": team_name,
                "members": [player for player in players],
                "numGames": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
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


def eloPlayerFor(team):
    player = pyelo.createPlayer(team['identifier'])
    for key in ['numGames', 'wins', 'losses', 'draws', 'elo', 'upsets', 'beenUpset']:
        setattr(player, key, team[key])
    return player


def applyEloStatsTo(player, team):
    for key in ['numGames', 'wins', 'losses', 'draws', 'elo', 'upsets', 'beenUpset']:
        team[key] = getattr(player, key)


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


@scheduler_fn.on_schedule(schedule="*/5 * * * *", timeout_sec=300)
def check_lobbies(event: scheduler_fn.ScheduledEvent) -> None:
    recent_lobbies = get_lobbies()
    print(f'Found lobbies {len(recent_lobbies)}')

    pyelo.setMean(ELO_MEAN)
    pyelo.setK(ELO_K)
    pyelo.setRPA(ELO_RPA)

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
            teams = get_or_create_teams(db, match)
            if len(teams) > 2:
                print('More than two teams')
                continue
            if len(teams) < 2:
                print('Only one player team')
                continue

            firstProfile = match['match']['profileMatches'][0]
            firstTeamWon = str(
                firstProfile['profile']['profileId']) in teams[0]['identifier']
            if firstProfile['decision'] == 'loss':
                firstTeamWon = not firstTeamWon

            winningTeam = teams[0] if firstTeamWon else teams[1]
            loosingTeam = teams[1] if firstTeamWon else teams[0]

            print(f'{winningTeam["name"]} won against {loosingTeam["name"]}')

            winningEloTeam = eloPlayerFor(winningTeam)
            loosingEloTeam = eloPlayerFor(loosingTeam)

            wonElo = winningEloTeam.elo
            lostElo = loosingEloTeam.elo
            match['winnerMMR'] = winningEloTeam.elo
            match['looserMMR'] = loosingEloTeam.elo

            pyelo.addGameResults(winningEloTeam, 1, loosingEloTeam, 0, 0, 0, 0)

            wonElo = winningEloTeam.elo - wonElo
            lostElo = loosingEloTeam.elo - lostElo
            match['wonElo'] = wonElo
            match['lostElo'] = lostElo
            match['participants'] = [
                winningTeam['identifier'],
                loosingTeam['identifier'],
            ]
            match_ref.set(match)

            applyEloStatsTo(winningEloTeam, winningTeam)
            applyEloStatsTo(loosingEloTeam, loosingTeam)

            print(
                f"Saving Players new elos: {winningTeam['name']}-{winningTeam['elo']} and {loosingTeam['name']}-{loosingTeam['elo']}")
            playersCol = db.collection('players')

            winningTeam['lastMatchAt'] = match['createdAt']
            loosingTeam['lastMatchAt'] = match['createdAt']
            playersCol.document(winningTeam['identifier']).set(winningTeam)
            playersCol.document(loosingTeam['identifier']).set(loosingTeam)

    print("Done")
# TODO:
# Support uploading of replays
# Determine if a match already exists by players and rough time
# Ensure the replay had the mod
# Adjust player MMR
