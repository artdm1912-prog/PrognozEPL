import os
import json
import math
import requests

API_KEY = os.environ.get("FOOTBALL_API_KEY")
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# ID Премьер-лиги Англии в API-Football
LEAGUE_ID = 39

def get_current_season():
    url = "https://v3.football.api-sports.io/leagues"
    res = requests.get(url, headers=HEADERS, params={"id": LEAGUE_ID}).json()
    seasons = res.get("response", [])[0].get("seasons", [])
    current = [s for s in seasons if s.get("current")]
    return current[0]["year"] if current else 2024

def fetch_upcoming_fixtures(season):
    url = "https://v3.football.api-sports.io/fixtures"
    params = {
        "league": LEAGUE_ID,
        "season": season,
        "next": 10
    }
    res = requests.get(url, headers=HEADERS, params=params).json()
    return res.get("response", [])

def get_team_avg_stats(team_id, season):
    url = "https://v3.football.api-sports.io/teams/statistics"
    params = {
        "league": LEAGUE_ID,
        "season": season,
        "team": team_id
    }
    res = requests.get(url, headers=HEADERS, params=params).json()
    resp = res.get("response", {})
    fixtures_played = resp.get("fixtures", {}).get("played", {}).get("total", 0) or 1
    
    goals_for = float(resp.get("goals", {}).get("for", {}).get("average", {}).get("total", 1.4) or 1.4)
    goals_against = float(resp.get("goals", {}).get("against", {}).get("average", {}).get("total", 1.2) or 1.2)

    return {
        "goals": round(goals_for, 2),
        "xg": round(goals_for * 0.95, 2),
        "sot": round(goals_for * 2.8, 1),
        "sh": round(goals_for * 5.5, 1),
        "cr": round(4.5 + goals_for, 1)
    }

def poisson_prob(k, lmbda):
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def calculate_match_card(home_stats, away_stats):
    m1_h, m1_a = home_stats["xg"], away_stats["xg"]
    m2_h, m2_a = home_stats["sot"] * 0.38, away_stats["sot"] * 0.28
    m3_h, m3_a = home_stats["goals"], away_stats["goals"]
    m4_h, m4_a = home_stats["sh"] * 0.14, away_stats["sh"] * 0.09
    m5_h, m5_a = home_stats["cr"] * 0.34, away_stats["cr"] * 0.23

    fin_h = round(m1_h*0.35 + m2_h*0.25 + m3_h*0.20 + m4_h*0.10 + m5_h*0.10, 2)
    fin_a = round(m1_a*0.35 + m2_a*0.25 + m3_a*0.20 + m4_a*0.10 + m5_a*0.10, 2)

    p_itb2_h = sum(poisson_prob(i, fin_h) for i in range(2, 6))
    p_tb25 = 0
    p_btts = 0
    for i in range(6):
        for j in range(6):
            prob = poisson_prob(i, fin_h) * poisson_prob(j, fin_a)
            if i + j > 2.5:
                p_tb25 += prob
            if i >= 1 and j >= 1:
                p_btts += prob

    return {
        "xScore": f"{fin_h} : {fin_a}",
        "score": f"{round(fin_h)} : {round(fin_a)}",
        "p_tb25": round(p_tb25 * 100, 1),
        "p_btts": round(p_btts * 100, 1),
        "p_itb2_h": round(p_itb2_h * 100, 1)
    }

def main():
    if not API_KEY:
        print("API Key not found!")
        return

    season = get_current_season()
    fixtures = fetch_upcoming_fixtures(season)
    output_matches = []

    for f in fixtures:
        h_id = f["teams"]["home"]["id"]
        h_name = f["teams"]["home"]["name"]
        a_id = f["teams"]["away"]["id"]
        a_name = f["teams"]["away"]["name"]
        date = f["fixture"]["date"]

        h_stats = get_team_avg_stats(h_id, season)
        a_stats = get_team_avg_stats(a_id, season)
        calc = calculate_match_card(h_stats, a_stats)

        output_matches.append({
            "id": f["fixture"]["id"],
            "date": date,
            "home": h_name,
            "away": a_name,
            "home_logo": f["teams"]["home"]["logo"],
            "away_logo": f["teams"]["away"]["logo"],
            "home_stats": h_stats,
            "away_stats": a_stats,
            "prediction": calc
        })

    with open("matches.json", "w", encoding="utf-8") as out:
        json.dump({"updated_at": fixtures[0]["fixture"]["date"] if fixtures else "", "matches": output_matches}, out, ensure_ascii=False, indent=2)
    print("Matches updated successfully!")

if __name__ == "__main__":
    main()
