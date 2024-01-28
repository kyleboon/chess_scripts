pgn = open(f"{year}-classical.pgn", encoding="utf-8")
game = chess.pgn.read_game(pgn)
total_games = 0
games_won = 0
games_drawn = 0
games_lost = 0

while game:
    total_games = total_games + 1
    game = chess.pgn.read_game(pgn)

    termination = game.root().headers.get("Termination")
