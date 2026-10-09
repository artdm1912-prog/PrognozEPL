#!/usr/bin/env python3
"""PROGNOZ AI: verified PL fixtures + incremental five-factor match statistics.

No invented statistics, no cross-season fallback. Failed requests do not erase caches.
Secrets: FOOTBALL_DATA_TOKEN, FOOTBALLDATA_IO_KEY (GitHub Actions only).
"""
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
FIXTURE_URL = 'https://api.football-data.org/v4/competitions/PL/matches'
API_URL = FIXTURE_URL
FINAL_STATUSES = {'FINISHED', 'AWARDED'}
UPCOMING_DAYS = 21
MAX_UPCOMING = 30
STATS_BASE = 'https://footballdata.io/api/v1'
SEASON_ID = 103535  # Verified by actual API response: PL 2026/27
LEAGUE_ID = 15
MAX_NEW_MATCHES = 18  # at most 18 stats requests per run; 2 scheduled runs/week
MAX_LIST_PAGES = 4  # max four listing requests per run
METRICS = ('xg', 'shots', 'shots_on_target', 'corners')
CACHE = ROOT / 'stats_match_cache.json'
TEAM_OUT = ROOT / 'team_stats.json'
FIXTURES_OUT = ROOT / 'matches.json'


def atomic_json(path, data):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def load_cache():
    if not CACHE.exists():
        return {}
    data = json.loads(CACHE.read_text(encoding='utf-8'))
    if data.get('season_id') != SEASON_ID or not isinstance(data.get('matches'), dict):
        raise ValueError('Cache belongs to a different season or has invalid structure.')
    return data['matches']


def get_json(url, token, params=None, auth_type='bearer'):
    headers = {'Accept': 'application/json'}
    if auth_type == 'bearer':
        headers['Authorization'] = f'Bearer {token}'
    else:
        headers['X-Auth-Token'] = token
    r = requests.get(url, headers=headers, params=params, timeout=28)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or data.get('success') is False or data.get('errors'):
        raise ValueError(f'Invalid/error API response from {url}; will not substitute data')
    return data


def parse_stats(response, expected_id):
    d = response.get('data') or {}
    m, s = d.get('match') or {}, d.get('stats') or {}
    season, league = m.get('season') or {}, m.get('league') or {}
    if (m.get('match_id') != expected_id or season.get('season_id') != SEASON_ID
            or league.get('league_id') != LEAGUE_ID or m.get('status') != 'complete'):
        raise ValueError(f'Unverified match/season/league/status for {expected_id}')
    h, a = m.get('home_team') or {}, m.get('away_team') or {}
    score = m.get('score') or {}
    if (not isinstance(h.get('team_id'), int) or not isinstance(a.get('team_id'), int)
            or not h.get('team_name') or not a.get('team_name')
            or not isinstance(score.get('home'), int) or not isinstance(score.get('away'), int)):
        raise ValueError(f'Invalid teams or goals for match {expected_id}')
    metrics = {}
    for k in METRICS:
        values = s.get(k)
        if not isinstance(values, dict):
            raise ValueError(f'No {k} in match {expected_id}')
        pair = []
        for side in ('home', 'away'):
            v = values.get(side)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v > 1000:
                raise ValueError(f'Invalid {k}.{side} in match {expected_id}: {v!r}')
            pair.append(v)
        metrics[k] = pair
    return {'id': expected_id, 'date': m.get('match_date'), 'home_id': h['team_id'],
            'away_id': a['team_id'], 'home': h['team_name'], 'away': a['team_name'],
            'goals': [score['home'], score['away']], 'stats': metrics,
            'source': 'footballdata.io', 'season': '2026/27'}


def fetch_match_ids(token):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    ids = []
    for page in range(1, MAX_LIST_PAGES + 1):
        data = get_json(f'{STATS_BASE}/matches', token,
                        params={'from': '2026-08-01', 'to': now, 'league_id': LEAGUE_ID,
                                'season_id': SEASON_ID, 'status': 'complete', 'page': page, 'limit': 100})
        rows = data.get('data')
        if not isinstance(rows, list):
            raise ValueError('List endpoint did not return an array')
        for row in rows:
            season = row.get('season') or {}
            league = row.get('league') or {}
            if (row.get('status') == 'complete' and season.get('season_id') == SEASON_ID
                    and league.get('league_id') == LEAGUE_ID and isinstance(row.get('match_id'), int)):
                ids.append(row['match_id'])
        meta = data.get('meta') or {}
        pages = meta.get('total_pages')
        if not rows or (isinstance(pages, int) and page >= pages) or len(rows) < 100:
            break
    return list(dict.fromkeys(ids))


def aggregate(cache):
    teams = {}
    def entry(tid, name):
        key = str(tid)
        if key not in teams:
            teams[key] = {'id': tid, 'name': name, 'played': 0, 'home_played': 0, 'away_played': 0,
                          'totals': {k: {'for': 0, 'against': 0} for k in ('goals',) + METRICS},
                          'home': {'played': 0, 'totals': {k: {'for': 0, 'against': 0} for k in ('goals',) + METRICS}},
                          'away': {'played': 0, 'totals': {k: {'for': 0, 'against': 0} for k in ('goals',) + METRICS}}}
        return teams[key]
    for m in cache.values():
        for i, side in enumerate(('home', 'away')):
            t = entry(m[f'{side}_id'], m[side])
            t['played'] += 1
            t[f'{side}_played'] += 1
            t[side]['played'] += 1
            all_values = {'goals': m['goals'], **m['stats']}
            for k, pair in all_values.items():
                for target in (t['totals'][k], t[side]['totals'][k]):
                    target['for'] += pair[i]
                    target['against'] += pair[1-i]
    for t in teams.values():
        for obj in [t, t['home'], t['away']]:
            count = obj['played']
            obj['per_match'] = ({k: {axis: round(pair[axis] / count, 4) for axis in ('for', 'against')}
                                 for k, pair in obj['totals'].items()} if count else {})
    return teams


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
    # Competition match lists normally contain a `matches` array; season metadata
    # is attached to individual match objects rather than to the list envelope.
    # Validate EVERY match before writing anything to disk.
    for match in matches:
        season = match.get('season') or {}
        start_date = str(season.get('startDate') or '')
        if not start_date.startswith('2026-'):
            raise ValueError(
                f"Unconfirmed / wrong season for match {match.get('id')}: "
                f"startDate={start_date!r}. Snapshot unchanged."
            )
        match_competition = match.get('competition') or {}
        if match_competition.get('code') not in (None, 'PL'):
            raise ValueError(f"Wrong competition for match {match.get('id')}. Snapshot unchanged.")
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


def fetch_fixtures(token):
    from_old = get_json(FIXTURE_URL, token, params={'season': 2026}, auth_type='football-data')
    rows = from_old.get('matches')
    if not isinstance(rows, list) or not rows or (from_old.get('competition') or {}).get('code') != 'PL':
        raise ValueError('No verified PL fixture response')
    for m in rows:
        if not str((m.get('season') or {}).get('startDate') or '').startswith('2026-'):
            raise ValueError('Fixtures from unexpected season; refusing update')
    # Same validated snapshot structure as the working fixture updater.
    return build_snapshot(from_old, datetime.now(timezone.utc))


def main():
    token = os.getenv('FOOTBALLDATA_IO_KEY', '').strip()
    schedule_token = os.getenv('FOOTBALL_DATA_TOKEN', '').strip()
    if not token or not schedule_token:
        raise RuntimeError('Missing FOOTBALLDATA_IO_KEY or FOOTBALL_DATA_TOKEN GitHub secret')
    cache = load_cache()
    match_ids = fetch_match_ids(token)
    print(f'Current-season completed match IDs: {len(match_ids)}; already cached: {len(cache)}')
    new_ids = [i for i in match_ids if str(i) not in cache][:MAX_NEW_MATCHES]
    rejected = []
    for mid in new_ids:
        try:
            data = get_json(f'{STATS_BASE}/matches/{mid}/stats', token)
            cache[str(mid)] = parse_stats(data, mid)
        except (requests.RequestException, ValueError) as e:
            rejected.append(mid)
            print(f'Match {mid} rejected: {type(e).__name__}: {e}')
        time.sleep(.15)
    # Save validated rows even if some individual matches are unavailable.
    if cache:
        atomic_json(CACHE, {'season_id': SEASON_ID, 'league_id': LEAGUE_ID,
                            'updated_at': datetime.now(timezone.utc).isoformat(), 'matches': cache})
        teams = aggregate(cache)
        atomic_json(TEAM_OUT, {'season': '2026/27', 'league': 'АПЛ',
                               'source': 'footballdata.io', 'source_matches': len(cache),
                               'updated_at': datetime.now(timezone.utc).isoformat(), 'teams': teams,
                               'note': 'Verified match-derived averages, not forecasts. Incomplete team season until backfill finishes.'})
    fixtures = fetch_fixtures(schedule_token)
    atomic_json(FIXTURES_OUT, fixtures)
    print(f'Statistics: cached {len(cache)} complete matches; new {len(new_ids)-len(rejected)}; rejected {len(rejected)}.')
    print(f'Fixtures: {fixtures["verified_fixture_count"]} verified; upcoming {len(fixtures["matches"])}.')
    if rejected:
        print('Rejected IDs (never inferred):', rejected)


if __name__ == '__main__':
    main()
