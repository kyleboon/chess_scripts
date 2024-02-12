import requests
from datetime import datetime

HEADERS = { 'User-Agent': 'kyle.f.boon@gmail.com' }

def get_opponents(username):
    """Retrieve recent opponents of the given username."""
    user = fetch_chesscom_userprofile(username)
    (start_year, start_month) = timestamp_to_year_month(user.get("joined"))
    year_month_combinations = generate_year_month_combinations(start_year, start_month)

    opponents = set()
    for (year, month) in year_month_combinations:
        url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month}"
        response = requests.get(url, headers = HEADERS)
        if response.status_code != 200:
            print(f"Failed to retrieve games for {username} {response.status_code}")
            continue

        games = response.json().get('games', [])

        for game in games:
            opponent = game['white']['username'] if game['white']['username'].lower() != username.lower() else game['black']['username']
            opponents.add(opponent.lower())

    return opponents

def timestamp_to_year_month(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    return dt.year, dt.month

def generate_year_month_combinations(start_year, start_month):
    start_date = datetime(int(start_year), int(start_month), 1)
    current_date = datetime.now()

    combinations = []

    while start_date <= current_date:
        year_month_str = start_date.strftime("%Y-%m")
        combinations.append(year_month_str.split("-"))

        # Add one month to the date
        # Handle December separately to roll over the year
        if start_date.month == 12:
            start_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            start_date = start_date.replace(month=start_date.month + 1)

    return combinations

def check_fair_play_violations(opponent):
    """Check if the accounts have been closed for fair play violations."""
    profile = fetch_chesscom_userprofile(opponent)
    return profile.get('status') == "closed:fair_play_violations"

def fetch_chesscom_userprofile(username):
    """Fetches a chess.com user profile."""
    url = f" https://api.chess.com/pub/player/{username}"
    response = requests.get(url, headers = HEADERS)
    if response.status_code != 200:
        return {}

    return response.json()


def main(username):
    opponents = get_opponents(username)

    fair_play_violations = 0
    for opponent in opponents:
        if check_fair_play_violations(opponent) == True:
            fair_play_violations =  fair_play_violations + 1

    print(f"{fair_play_violations} accounts closed for fair_play_violations out of {len(opponents)}")

if __name__ == "__main__":
    user = input("Enter the Chess.com username: ")
    main(user)
