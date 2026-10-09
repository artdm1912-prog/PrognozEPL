#!/usr/bin/env python3
"""Fetch authentic 2026/27 Premier League fixtures from football-data.org.

One HTTP request per execution. Never invent team statistics or substitute seasons.
This replaces the former demo-only update_data.py, not the full five-factor engine.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_URL = 'https://api.football-data.org/v4/competitions/PL/matches'
SEASON_START_YEAR = 2026
OUTPUT_PATH = Path(__file__).resolve().parent / 'matches.json'
UPCOMING_DAYS = 21
MAX_UPCOMING = 30
FINAL_STATUSES = {'FINISHED', 'AWARDED'}


def convert_match(match):
    home = match.get('homeTeam') or {}
    away = match.get('awayTeam') or {}
    date = match.get('utcDate')
    if not (isinstance(match.get('id'), int) and date and home.get('id') and away.get('id')):
        return None
    result = {
        'id': match['id'],
        'date': date,
        'home': home.get('shortName') or home.get('name'),
        'away': away.get('shortName') or away.get('name'),
        'home_id': home['id'],
        'away_id': away['id'],
        'league': 'АПЛ',
        'season': '2026/27',
        'status': match.get('status', 'UNKNOWN'),
        'matchday': match.get('matchday'),
        'source': 'football-data.org',
        'statistics_verified': False,
        # No home_stats/away_stats: football-data.org does not supply these
        # required five-factor indicators in this endpoint.
    }
    full_time = (match.get('score') or {}).get('fullTime') or {}
    if match.get('status') in FINAL_STATUSES and isinstance(full_time.get('home'), int) and isinstance(full_time.get('away'), int):
        result['actual'] = [full_time['home'], full_time['away']]
    return result


def build_snapshot(payload, now):
    matches = payload.get('matches')
    if not isinstance(matches, list) or not matches:
        raise ValueError('API returned no fixtures. Refusing to replace snapshot.')
    competition = payload.get('competition') or {}
    if competition.get('code') != 'PL':
        raise ValueError('API response does not describe PL competition.')
    season = payload.get('season') or {}
    start_date = str(season.get('startDate') or '')
    # The API must actually confirm 2026/27, not just echo a requested query.
    if not start_date.startswith('2026-'):
        raise ValueError(f'Unexpected season start {start_date!r}; expected 2026/27.')
    parsed = [r for m in matches if (r := convert_match(m)) is not None]
    if not parsed:
        raise ValueError('No valid team fixtures returned.')
    lower = now - timedelta(days=1)
    upper = now + timedelta(days=UPCOMING_DAYS)
    window = []
    for m in parsed:
        try:
            dt = datetime.fromisoformat(m['date'].replace('Z', '+00:00'))
            if lower <= dt <= upper:
                window.append(m)
        except ValueError:
            continue
    window.sort(key=lambda m: m['date'])
    return {
        'updated_at': now.isoformat(),
        'season': '2026/27',
        'league': 'АПЛ',
        'source': API_URL,
        'verified_fixture_count': len(parsed),
        'statistics_verified': False,
        'note': 'Real schedule/scores only. xG, shots, corners and injury reports are NOT retrieved.',
        'matches': window[:MAX_UPCOMING],
    }


def main():
    token = os.getenv('FOOTBALL_DATA_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Missing FOOTBALL_DATA_TOKEN in GitHub Actions secrets.')
    response = requests.get(API_URL, headers={'X-Auth-Token': token, 'Accept': 'application/json'}, params={'season': SEASON_START_YEAR}, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if payload.get('error') or payload.get('errors'):
        raise RuntimeError('API returned an error; see response in provider dashboard.')
    snapshot = build_snapshot(payload, datetime.now(timezone.utc))
    temp_path = OUTPUT_PATH.with_suffix('.json.tmp')
    temp_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp_path.replace(OUTPUT_PATH)
    print(f"Retrieved {snapshot['verified_fixture_count']} verified PL fixtures; saved {len(snapshot['matches'])} within next {UPCOMING_DAYS} days.")
    print('Team advanced statistics not supplied; xScore is not calculated.')


if __name__ == '__main__':
    main()
