import requests
import datetime

T = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?{~}(^)[_]@#$,./&-*++="

def decode(n):
    w = len(n)
    C = []
    for i in range(0, w, 2):
        _ = {}
        o = T.index(n[i])
        s = T.index(n[i + 1])
        if s > 63:
            _["promotion"] = "qnrbkp"[int((s - 64) / 3)]
            s = o + (-8 if o < 16 else 8) + ((s - 1) % 3) - 1
        if o > 75:
            _["drop"] = "qnrbkp"[o - 79]
        else:
            _["from"] = T[o % 8] + str(int(o / 8) + 1)
        _["to"] = T[s % 8] + str(int(s / 8) + 1)
        C.append(_)
    return C[0]

username = "kyle_b81"
today = datetime.date.today()
last_month = today - datetime.timedelta(days=30)
date_range = f"{last_month.year}/{last_month.month:02d}"

# Construct the API URL for the games endpoint with the date range and username
url = f"https://api.chess.com/pub/player/{username}/games/{date_range}"

# Send a GET request to the API endpoint and store the response in a variable
response = requests.get(url)

# Extract the JSON data from the response
data = response.json()

# loop through each game and print the time control
for game in data["games"]:
    time_control  = game["time_control"]
    # split the time control string on the + to get the minutes and convert it to an int if it is one
    minutes = int(time_control.split("+")[0])

    if (minutes > 30):
        game_url = game["url"]
        # split the url string on the / to get the game id
        game_id = game_url.split("/")[-1]
       
        game_url = f"https://www.chess.com/callback/live/game/{game_id}"

        callback_response = requests.get(game_url)
        print(decode(callback_response.json()["game"]["moveList"]))