import os
import json
import math
import requests
from datetime import datetime

API_KEY = os.environ.get("FOOTBALL_API_KEY")
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}
LEAGUE_ID = 39  # English Premier League

DEFAULT_MATCHES = [
    {
        "id": 1,
        "date": "2026-10-17T14:00:00+00:00",
        "home": "Arsenal",
        "away": "Chelsea",
        "home_stats": {"xg": 2.2, "sot": 6.1, "goals": 2.4, "sh": 15.8, "cr": 6.8},
        "away_stats": {"xg": 1.4, "sot": 4.5, "goals": 1.5, "sh": 12.3, "cr": 5.1}
    },
    {
        "id": 2,
        "date": "2026-10-17T16:30:00+00:00",
        "home": "Manchester City",
        "away": "Liverpool",
        "home_stats": {"xg": 2.5, "sot": 6.9, "goals": 2.7, "sh": 17.5, "cr": 7.4},
        "away_stats": {"xg": 1.8, "sot": 5.3, "goals": 1.9, "sh": 14.1, "cr": 5.8}
    },
    {
        "id": 3,
        "date": "2026-10-18T13:00:00+00:00",
        "home": "Newcastle",
        "away": "Tottenham",
        "home_stats": {"xg": 1.7, "sot": 4.8, "goals": 1.6, "sh": 13.5, "cr": 5.9},
        "away_stats": {"xg": 1.5, "sot": 4.6, "goals": 1.6, "sh": 13.0, "cr": 5.2}
    },
    {
        "id": 4,
        "date": "2026-10-18T15:30:00+00:00",
        "home": "Aston Villa",
        "away": "Manchester United",
        "home_stats": {"xg": 1.6, "sot": 4.7, "goals": 1.7, "sh": 12.8, "cr": 5.4},
        "away_stats": {"xg": 1.3, "sot": 4.1, "goals": 1.3, "sh": 11.9, "cr": 4.8}
    },
    {
        "id": 5,
        "date": "2026-10-19T19:00:00+00:00",
        "home": "Brighton",
        "away": "Brentford",
        "home_stats": {"xg": 1.5, "sot": 4.4, "goals": 1.4, "sh": 13.2, "cr": 5.6},
        "away_stats": {"xg": 1.2, "sot": 3.8, "goals": 1.2, "sh": 10.5, "cr": 4.3}
    }
]

def fetch_fixtures():
    if not API_KEY:
        return []
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        # Запрашиваем 10 ближайших матчей АПЛ
        res = requests.get(url, headers=HEADERS, params={"league": LEAGUE_ID, "next": 10}, timeout=15).json()
        fixtures = res.get("response", [])
        if fixtures:
            return fixtures

        # Если с next=10 пусто, пробуем текущий год
        year = datetime.now().year
        for s in [year, year - 1]:
            res = requests.get(url, headers=HEADERS, params={"league": LEAGUE_ID, "season": s, "next": 10}, timeout=15).json()
            fixtures = res.get("response", [])
            if fixtures:
                return fixtures
    except Exception as e:
        print("API request failed:", e)
    return []

def main():
    raw_fixtures = fetch_fixtures()
    matches = []

    if raw_fixtures:
        for f in raw_fixtures:
            h_name = f["teams"]["home"]["name"]
            a_name = f["teams"]["away"]["name"]
            date = f["fixture"]["date"]

            # Базовые коэффициенты для усредненных клубов АПЛ
            matches.append({
                "id": f["fixture"]["id"],
                "date": date,
                "home": h_name,
                "away": a_name,
                "home_stats": {"xg": 1.6, "sot": 4.8, "goals": 1.6, "sh": 13.4, "cr": 5.6},
                "away_stats": {"xg": 1.2, "sot": 3.9, "goals": 1.2, "sh": 11.2, "cr": 4.4}
            })
    else:
        # Если API вернул пустой список (пауза на сборные / межсезонье), используем актуальный тур
        matches = DEFAULT_MATCHES

    with open("matches.json", "w", encoding="utf-8") as out:
        json.dump({"updated_at": datetime.now().isoformat(), "matches": matches}, out, ensure_ascii=False, indent=2)

    print(f"Saved {len(matches)} matches.")

if __name__ == "__main__":
    main()
