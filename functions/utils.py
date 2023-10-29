import datetime
# The Firebase Admin SDK to delete users.
from datetime import datetime, timedelta

import google.cloud.firestore
import pyelo
import requests
from firebase_admin import firestore, initialize_app
from firebase_functions import scheduler_fn
from google.cloud.firestore_v1.base_query import FieldFilter

ELO_MEAN = 2500
ELO_K = 80
ELO_RPA = 800


def init_pyelo():
    pyelo.setMean(ELO_MEAN)
    pyelo.setK(ELO_K)
    pyelo.setRPA(ELO_RPA)


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
                "region": players[0].regionId,
                "realm": players[0].realmId,
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


def generate_team_identifier(players):
    # Extract profile IDs, sort them, and then join them into a string
    ids = [str(player["profileId"]) for player in players]
    ids.sort()
    return "-".join(ids)


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


def handle_match(db, match_ref, match):
    init_pyelo()

    teams = get_or_create_teams(db, match)
    if len(teams) > 2:
        print('More than two teams')
        return
    if len(teams) < 2:
        print('Only one player team')
        return

    firstProfile = match['match']['profileMatches'][0]
    firstTeamWon = str(
        firstProfile['profile']['profileId']) in teams[0]['identifier']
    if firstProfile['decision'] == 'loss':
        firstTeamWon = not firstTeamWon

    # TODO: Handle tie/etcZ

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
    if match_ref:
        match_ref.set(match)
    else:
        match_ref = db.collection('matches').add(match)

    applyEloStatsTo(winningEloTeam, winningTeam)
    applyEloStatsTo(loosingEloTeam, loosingTeam)

    print(
        f"Saving Players new elos: {winningTeam['name']}-{winningTeam['elo']} and {loosingTeam['name']}-{loosingTeam['elo']}")
    playersCol = db.collection('players')

    winningTeam['lastMatchAt'] = match['createdAt']
    loosingTeam['lastMatchAt'] = match['createdAt']
    playersCol.document(winningTeam['identifier']).set(winningTeam)
    playersCol.document(loosingTeam['identifier']).set(loosingTeam)
