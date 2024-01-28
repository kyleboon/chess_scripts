import chess.pgn
import requests

username = "kyle_b81"
year = "2022"
number_of_months = 8

with open(f"{year}.pgn", "w") as output_file:
    for month_index in range(number_of_months):
        api = f"https://api.chess.com/pub/player/{username}/games/{year}/{str(month_index + 1).zfill(2)}"
        results = requests.get(api).json()

        for next_game in results['games']:
            if next_game['time_class'] == 'rapid':
                if next_game['time_class'] == 'rapid':
                    output_file.write(next_game['pgn'])
                    output_file.write("\n\n")

pgn = open(f"{year}.pgn", encoding="utf-8")
game = chess.pgn.read_game(pgn)
while game:
    minutes = int(game.headers["TimeControl"].split('+')[0])
    if minutes > 2699:
        print(game, file=open(f"{year}-classical.pgn", "a"), end="\n\n")
    game = chess.pgn.read_game(pgn)