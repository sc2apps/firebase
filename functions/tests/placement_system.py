import pyelo
from utils import ELO_K, ELO_MEAN, ELO_RPA, multipliers_for


def test_3_person_scenario(use_muls=True):
    eloSystem = pyelo.Elo(ELO_MEAN, ELO_K, ELO_RPA)

    newPlayer = pyelo.Player("noob")
    newPlayer.elo = ELO_MEAN
    fiveGameAcct = pyelo.Player("other")
    fiveGameAcct.elo = ELO_MEAN
    experiencedPlayer = pyelo.Player("vet")
    experiencedPlayer.elo = ELO_MEAN*1.25

    experiencedPlayer.wins = 50
    experiencedPlayer.numGames = 80
    experiencedPlayer.losses = 30

    # Add 5 games against randoms
    for i in range(0, 5):
        print(f"Adding i {i}")
        randomPlayer = pyelo.Player(f"random{i}")
        randomPlayer.elo = ELO_MEAN
        muls = multipliers_for(
            fiveGameAcct, randomPlayer) if use_muls else (1, 1)
        eloSystem.addGame(fiveGameAcct, 1, randomPlayer,
                          0, 0, 0, 0, muls[0], muls[1])
    print(f"Five game elo {fiveGameAcct.elo}")

    for i in range(0, 5):
        muls = multipliers_for(newPlayer, fiveGameAcct) if use_muls else (1, 1)
        eloSystem.addGame(
            newPlayer, 1, fiveGameAcct, 0, 0, 0, 0,
            muls[0], muls[1]
        )
        print(
            f"After Noob elo: {newPlayer.elo}, fiveGameAcct elo: {fiveGameAcct.elo} - muls: {muls}")

    print(
        f"Before noob elo: {newPlayer.elo}, vet elo: {experiencedPlayer.elo}")
    for i in range(0, 5):
        muls = multipliers_for(
            experiencedPlayer, newPlayer) if use_muls else (1, 1)
        eloSystem.addGame(
            experiencedPlayer, 1, newPlayer, 0, 0, 0, 0,
            muls[0], muls[1]
        )
        print(
            f"After Noob elo: {newPlayer.elo}, vet elo: {experiencedPlayer.elo} - muls: {muls}")


def test_2_person_scenario(use_muls=True):
    eloSystem = pyelo.Elo(ELO_MEAN, ELO_K, ELO_RPA)

    newPlayer = pyelo.Player("noob")
    newPlayer.elo = ELO_MEAN
    fiveGameAcct = pyelo.Player("other")
    fiveGameAcct.elo = ELO_MEAN

    # Add 5 games against randoms
    for i in range(0, 5):
        randomPlayer = pyelo.Player(f"random{i}")
        randomPlayer.elo = ELO_MEAN
        muls = multipliers_for(
            fiveGameAcct, randomPlayer) if use_muls else (1, 1)
        eloSystem.addGame(fiveGameAcct, 1, randomPlayer,
                          0, 0, 0, 0, muls[0], muls[1])
    print(f"Five game elo {fiveGameAcct.elo}")

    for i in range(0, 5):
        muls = multipliers_for(newPlayer, fiveGameAcct) if use_muls else (1, 1)
        eloSystem.addGame(
            newPlayer, 1, fiveGameAcct, 0, 0, 0, 0,
            muls[0], muls[1]
        )
        print(
            f"After Noob elo: {newPlayer.elo}, fiveGameAcct elo: {fiveGameAcct.elo} - muls: {muls}")

    print(
        f"Before noob elo: {newPlayer.elo}, vet elo: {fiveGameAcct.elo}")
    for i in range(0, 5):
        muls = multipliers_for(fiveGameAcct, newPlayer) if use_muls else (1, 1)
        eloSystem.addGame(
            fiveGameAcct, 1, newPlayer, 0, 0, 0, 0,
            muls[0], muls[1]
        )
        print(
            f"After Noob elo: {newPlayer.elo}, vet elo: {fiveGameAcct.elo} - muls: {muls}")
