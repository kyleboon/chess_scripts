import requests
import os
import json
import logging
import math
import chess
import chess.pgn
import chess.engine
import chess.variant

# Constants
ERROR_THRESHOLD = {
    'BLUNDER': -300,
    'MISTAKE': -150,
    'DUBIOUS': -75,
}
NEEDS_ANNOTATION_THRESHOLD = 7.5
MAX_SCORE = 10000
MAX_CPL = 2000
SHORT_PV_LEN = 10

def eval_numeric(info):
    """
    Returns a numeric evaluation of the position, even if depth-to-mate was
    found. This facilitates comparing numerical evaluations with depth-to-mate
    evaluations
    """
    return info['score'].white().score(mate_score=10_000)


def eval_absolute(number, white_to_move):
    """
    Accepts a relative evaluation (from the point of view of the player to
    move) and returns an absolute evaluation (from the point of view of white)
    """

    return number if white_to_move else -number

def judge_move(board, played_move, engine):
    """
    Evaluate the strength of a given move by comparing it to engine's best
    move and evaluation at a given depth, in a given board context
    Returns a judgment
    A judgment is a dictionary containing the following elements:
          "bestmove":      The best move in the position, according to the
                           engine
          "besteval":      A numeric evaluation of the position after the best
                           move is played
          "bestcomment":   A plain-text comment appropriate for annotating the
                           best move
          "pv":            The engine's primary variation including the best
                           move
          "playedeval":    A numeric evaluation of the played move
          "playedcomment": A plain-text comment appropriate for annotating the
                           played move
          "depth":         Search depth in plies
          "nodes":         Number nodes searched
    """

    judgment = {}

    info = engine.analyse(board, chess.engine.Limit(depth=22))
    judgment["bestmove"] = info["pv"][0]
    judgment["besteval"] = eval_numeric(info)

    # If the played move matches the engine bestmove, we're done
    if played_move == judgment["bestmove"]:
        judgment["playedeval"] = judgment["besteval"]
    else:
        # get the engine evaluation of the played move
        board.push(played_move)
        info = engine.analyse(board, chess.engine.Limit(depth=22))

        # Store the numeric evaluation.
        # We invert the sign since we're now evaluating from the opponent's
        # perspective
        judgment["playedeval"] = eval_numeric(info)

        # Take the played move off the stack (reset the board)
        board.pop()

    return judgment

def truncate_pv(board, pv):
    """
    If the pv ends the game, return the full pv
    Otherwise, return the pv truncated to 10 half-moves
    """

    for move in pv:
        if not board.is_legal(move):
            raise AssertionError
        board.push(move)

    if board.is_game_over(claim_draw=True):
        return pv
    else:
        return pv[:SHORT_PV_LEN]


def eco_fen(board):
    """
    Takes a board position and returns a FEN string formatted for matching with
    eco.json
    """
    board_fen = board.board_fen()
    castling_fen = board.castling_xfen()

    to_move = 'w' if board.turn else 'b'

    return "{} {} {}".format(board_fen, to_move, castling_fen)


def cpl(string):
    """
    Centipawn Loss
    Takes a string and returns an integer representing centipawn loss of the
    move We put a ceiling on this value so that big blunders don't skew the
    acpl too much
    """

    cpl = int(string)

    return min(cpl, MAX_CPL)


def acpl(cpl_list):
    """
    Average Centipawn Loss
    Takes a list of integers and returns an average of the list contents
    """
    try:
        return sum(cpl_list) / len(cpl_list)
    except ZeroDivisionError:
        return 0


def clean_game(game):
    """
    Takes a game and strips all comments and variations, returning the
    "cleaned" game
    """
    node = game.end()

    while True:
        prev_node = node.parent

        node.comment = None
        node.nags = []
        for variation in reversed(node.variations):
            if not variation.is_main_variation():
                node.remove_variation(variation)

        if node == game.root():
            break

        node = prev_node

    return node.root()


def game_length(game):
    """
    Takes a game and returns an integer corresponding to the number of
    half-moves in the game
    """
    ply_count = 0
    node = game.end()

    while not node == game.root():
        node = node.parent
        ply_count += 1

    return ply_count

def classify_fen(fen, ecodb):
    """
    Searches a JSON file with Encyclopedia of Chess Openings (ECO) data to
    check if the given FEN matches an existing opening record
    Returns a classification
    A classfication is a dictionary containing the following elements:
        "code":         The ECO code of the matched opening
        "desc":         The long description of the matched opening
        "path":         The main variation of the opening
    """
    classification = {}
    classification["code"] = ""
    classification["desc"] = ""
    classification["path"] = ""

    for opening in ecodb:
        if opening['fen'] == fen:
            classification["code"] = opening['eco']
            classification["desc"] = opening['name']
            classification["path"] = opening['moves']

    return classification

def classify_opening(game):
    """
    Takes a game and adds an ECO code classification for the opening
    Returns the classified game and root_node, which is the node where the
    classification was made
    """
    ecopath = os.path.join(os.path.dirname(__file__), 'eco.json')
    with open(ecopath, 'r') as ecofile:
        ecodata = json.load(ecofile)

        ply_count = 0

        root_node = game.root()
        node = game.end()

        while not node == game.root():
            prev_node = node.parent

            fen = eco_fen(node.board())
            classification = classify_fen(fen, ecodata)

            if classification["code"] != "":
                # Add some comments classifying the opening
                node.root().headers["ECO"] = classification["code"]
                node.root().headers["Opening"] = classification["desc"]
                node.comment = "{} {}".format(classification["code"],
                                              classification["desc"])
                # Remember this position so we don't analyze the moves
                # preceding it later
                root_node = node
                # Break (don't classify previous positions)
                break

            ply_count += 1
            node = prev_node

        node.root().headers["Moves"] = str(ply_count)
        return node.root(), root_node, ply_count


def add_acpl(game, root_node):
    """
    Takes a game and a root node, and adds PGN headers with the computed ACPL
    (average centipawn loss) for each player. Returns a game with the added
    headers.
    """
    white_cpl = []
    black_cpl = []

    node = game.end()
    while not node == root_node:
        prev_node = node.parent

        judgment = node.comment
        delta = judgment["besteval"] - judgment["playedeval"]

        if node.board().turn:
            black_cpl.append(cpl(delta))
        else:
            white_cpl.append(cpl(delta))

        node = prev_node

    node.root().headers["WhiteACPL"] = str(round(acpl(white_cpl)))
    node.root().headers["BlackACPL"] = str(round(acpl(black_cpl)))

    return node.root()

def analyze_game(game, engine):
    """
    Take a PGN game and return a GameNode with engine analysis added
    - Attempt to classify the opening with ECO and identify the root node
        * The root node is the position immediately after the ECO
        classification
        * This allows us to skip analysis of moves that have an ECO
        classification
    - Analyze the game, adding annotations where appropriate
    - Return the root node with annotations
    """
    # First, check the game for PGN parsing errors
    # This is done so that we don't waste CPU time on nonsense games
    checkgame(game)

    ###########################################################################
    # Clear existing comments and variations
    ###########################################################################
    game = clean_game(game)

    ###########################################################################
    # Attempt to classify the opening and calculate the game length
    ###########################################################################
    game, root_node, ply_count = classify_opening(game)

    node = game.end()
    while not node == root_node:
        prev_node = node.parent
        node.comment = judge_move(prev_node.board(), node.move, engine)
        node = prev_node

    return add_acpl(game, root_node)


def checkgame(game):
    """
    Check for PGN parsing errors and abort if any were found
    This prevents us from burning up CPU time on nonsense positions
    """
    if game.errors:
        errormsg = "There were errors parsing the PGN game:"
        raise RuntimeError(errormsg)

    # Try to verify that the PGN file was readable
    if game.end().parent is None:
        errormsg = "Could not render the board. Is the file legal PGN?" \
            "Aborting..."
        raise RuntimeError(errormsg)

def main():
    try:
        engine = chess.engine.SimpleEngine.popen_uci("stockfish")
    except FileNotFoundError:
        raise
    except PermissionError:
        raise

    user_name = 'kyle_b81'

    with open("january2022.pgn", "w") as output_file:
        for month_index in range(1):
            api = f"https://api.chess.com/pub/player/{user_name}/games/2022/{str(month_index + 1).zfill(2)}"
            print(api)
            results = requests.get(api).json()

            for next_game in results['games']:
                if next_game['time_class'] == 'rapid':
                    output_file.write(next_game['pgn'])
                    output_file.write("\n\n")

    pgn = open("january2022.pgn", encoding="utf-8")

    game = chess.pgn.read_game(pgn)
    while game:
        if (game.root().headers["Termination"].startswith("kyle_b81 won")):
            analyzed_game = analyze_game(game, engine)
            if (analyzed_game.root().headers["White"] == user_name):
                acpl = analyzed_game.root().headers["WhiteACPL"]
            else:
                acpl = analyzed_game.root().headers["BlackACPL"]

            print(acpl+"\t"+analyzed_game.root().headers["Link"])
        game = chess.pgn.read_game(pgn)

    engine.quit()

if __name__ == "__main__":
    main()