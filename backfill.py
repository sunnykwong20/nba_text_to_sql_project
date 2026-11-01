"""
Backfill team_info_common from the live NBA Stats API via nba_api.

team_info_common needs ONE ROW PER (team_id, season) — not one row per team —
since w/l/pct/conf_rank/div_rank/pts_rank/etc. are season-level stats, not
fixed team attributes. The needed (team_id, season) pairs are derived from
the `game` table (regular season only, since the rank/record columns here
are regular-season standings).

REWRITE NOTE (why this isn't the original per-season-call version):
The first version called `TeamInfoCommon` once per (team, season) pair,
passing `season_nullable` to request a specific historical season. Live
testing showed `TeamInfoCommon` silently ignores `season_nullable` and
always returns the team's *current* season snapshot — so every historical
attempt returned the same (team, current_season) row. The first season
attempted per team (earliest first, since attempts were sorted chronologically)
inserted successfully; every other season attempted for that same team then
collided with that same row and failed with `UNIQUE constraint failed`. Net
result: one real row per team (always labeled with the current season),
plus a large pile of harmless-but-confusing constraint-failure noise, and
zero actual historical data.

This version calls `TeamYearByYearStats` once per team instead. That
endpoint returns one row per season in a single response — which is both
the data this table actually needs, and ~98% fewer API calls (~30 team
calls instead of ~2,000+ team-season calls).

Team identity fields that don't vary by season in the data available here
(city, name, abbreviation, conference, division, code, slug, min/max year)
still come from `TeamInfoCommon`, called once per team.
KNOWN LIMITATION: a team that relocated/rebranded (e.g. Seattle -> OKC) will
be tagged with its *current* identity on every historical row, not its
historical identity at the time, since there's no confirmed
historical-identity endpoint wired up here.

Defunct early-era franchises (e.g. the Anderson Packers, one season in
1949-50) show up in local historical game data but have no team-level
history on the live API — these are filtered out of `needed` up front,
against nba_api's static list of current franchises, rather than left to
fail on every call.

NOTE on current season: TeamYearByYearStats doesn't carry the still-in-progress
current season, and `needed` (derived from your local `game` table) won't
include it either until that table has this season's games. That's fine —
rerun this script later once it does, and it'll pick that season up like any
other.

NOTE on types: values pulled from a pandas row are numpy scalars
(numpy.int64, numpy.float64, ...), not plain Python int/float. sqlite3
doesn't reliably adapt numpy.int64 — it can silently land as a BLOB column
instead of INTEGER. Every value pulled from a dataframe goes through
_to_native() before being inserted, specifically to avoid this.

BEFORE RUNNING THE FULL BACKFILL: run with TEST_LIMIT = 1 first and read the
logged output closely. It prints:
  - the real `TeamYearByYearStats` column names for that one team, and
  - a one-time warning naming any of SEASON_STAT_SOURCES's target columns it
    could not find a matching source column for.
This script's column mapping is written from documented/known nba_api
response shapes but hasn't been confirmed against your installed version's
exact field names — in particular PTS_RANK/REB_RANK/AST_RANK/OPP_PTS* are
uncertain. Missing columns are inserted as NULL and logged, never guessed.

Resumable: before each run, it diffs what's needed against what's already in
team_info_common, so re-running after an interruption only fetches what's
still missing.
"""

import logging
import sqlite3
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import teaminfocommon, teamyearbyyearstats
from nba_api.stats.static import teams as static_teams

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # still prints to the terminal as before
        logging.FileHandler("backfill_run.log", mode="w"),  # and saves a full copy here
    ],
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "text_to_sql_project" /"data" / "nba.sqlite"  # adjust if your script lives elsewhere
REQUEST_DELAY_SECONDS = 1.0  # be polite to the NBA Stats API; raise this if you hit timeouts/429s
REGULAR_SEASON_ONLY = True   # team_info_common's rank/record stats are regular-season standings
TEST_LIMIT = None            # set to e.g. 1 for a dry run before the full backfill (limits TEAMS, not seasons)

LEAGUE_ID = "00"  # NBA

# Target team_info_common columns that come from a per-season row in
# TeamYearByYearStats, mapped to the candidate source column name(s) to try
# in order (first match wins). Confirm the real names via a TEST_LIMIT=1 run
# — anything not found here is inserted as NULL and logged once, not guessed.
SEASON_STAT_SOURCES = {
    "w": ["WINS"],
    "l": ["LOSSES"],
    "pct": ["WIN_PCT"],
    "conf_rank": ["CONF_RANK"],
    "div_rank": ["DIV_RANK"],
    "pts_rank": ["PTS_RANK"],
    "pts_pg": ["PTS"],
    "reb_rank": ["REB_RANK"],
    "reb_pg": ["REB"],
    "ast_rank": ["AST_RANK"],
    "ast_pg": ["AST"],
    "opp_pts_rank": ["OPP_PTS_RANK"],
    "opp_pts_pg": ["OPP_PTS", "OPP_PTS_PG"],
}

# Target columns that are team identity, not season stats — fetched once per
# team from TeamInfoCommon (confirmed working/reachable earlier) rather than
# once per season.
IDENTITY_COLUMNS = {
    "team_city": "TEAM_CITY",
    "team_name": "TEAM_NAME",
    "team_abbreviation": "TEAM_ABBREVIATION",
    "team_conference": "TEAM_CONFERENCE",
    "team_division": "TEAM_DIVISION",
    "team_code": "TEAM_CODE",
    "team_slug": "TEAM_SLUG",
    "min_year": "MIN_YEAR",
    "max_year": "MAX_YEAR",
}

_missing_columns_warned: set[str] = set()


def season_id_to_season_str(season_id: str) -> str:
    """Convert game.season_id (e.g. '22023') to nba_api's season format ('2023-24')."""
    start_year = int(season_id[-4:])
    end_year_2digit = str((start_year + 1) % 100).zfill(2)
    return f"{start_year}-{end_year_2digit}"


def season_str_to_season_id(season_str: str) -> str:
    """Inverse of the above — reconstructs the regular-season season_id
    ('2' prefix) team_info_common stores, e.g. '2023-24' -> '22023'."""
    start_year = season_str[:4]
    return f"2{start_year}"


def get_needed_team_seasons(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    """Distinct (team_id, season_str) pairs that should exist in team_info_common,
    derived from the game table's home and away team/season columns."""
    query = """
        SELECT DISTINCT team_id, season_id, season_type FROM (
            SELECT team_id_home AS team_id, season_id, season_type FROM game
            UNION
            SELECT team_id_away AS team_id, season_id, season_type FROM game
        )
    """
    rows = conn.execute(query).fetchall()
    if REGULAR_SEASON_ONLY:
        rows = [r for r in rows if r[2] == "Regular Season"]
    return {(team_id, season_id_to_season_str(season_id)) for team_id, season_id, _ in rows}


def get_existing_team_seasons(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT team_id, season_year FROM team_info_common").fetchall()
    return {(str(team_id), season_year) for team_id, season_year in rows}


def get_valid_team_ids() -> set[str]:
    """Current NBA franchises recognized by the live stats API. Defunct early-era
    teams (e.g. the Anderson Packers, one season in 1949-50, folded before the
    NBA's modern lineage settled) show up in local historical game data but have
    no team-level history in TeamInfoCommon / TeamYearByYearStats — the live API
    only tracks currently active franchises, so calls for them fail with an
    empty/non-JSON response rather than a clean 404."""
    return {str(t["id"]) for t in static_teams.get_teams()}


def group_by_team(pairs: set[tuple[str, str]]) -> dict[str, set[str]]:
    by_team: dict[str, set[str]] = {}
    for team_id, season_str in pairs:
        by_team.setdefault(team_id, set()).add(season_str)
    return by_team


def _to_native(value):
    """Values pulled from a pandas row are numpy scalars (numpy.int64,
    numpy.float64, ...), not plain Python int/float. sqlite3 doesn't adapt
    those reliably — depending on your Python/sqlite3 version they can
    silently land as a BLOB column instead of INTEGER/REAL. .item() converts
    a numpy scalar to its native Python equivalent; anything else (already a
    plain Python value, or None) passes through unchanged."""
    if value is None:
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def fetch_team_identity(team_id: str) -> dict:
    response = teaminfocommon.TeamInfoCommon(team_id=int(team_id))
    info_df = response.get_data_frames()[0]
    row = info_df.iloc[0]
    return {target: _to_native(row[source]) for target, source in IDENTITY_COLUMNS.items()}


def fetch_team_history(team_id: str) -> pd.DataFrame:
    """One call per team, every season back. This is what fixes the original
    bug — no per-season `season_nullable` request that the API ignored."""
    response = teamyearbyyearstats.TeamYearByYearStats(
        team_id=int(team_id),
        per_mode_simple="PerGame",
        season_type_all_star="Regular Season" if REGULAR_SEASON_ONLY else "Playoffs",
    )
    return response.get_data_frames()[0]


def extract_season_stats(history_df: pd.DataFrame, season_str: str, log_missing: bool) -> dict:
    """Pull one season's row out of the team's full history and map it onto
    team_info_common's stat columns. A source column that isn't found is
    inserted as NULL and logged once — never guessed at or silently dropped."""
    season_rows = history_df[history_df["YEAR"] == season_str]
    if season_rows.empty:
        return {}

    source_row = season_rows.iloc[0]
    stats = {}
    for target, candidates in SEASON_STAT_SOURCES.items():
        value = None
        for candidate in candidates:
            if candidate in source_row.index:
                value = _to_native(source_row[candidate])
                break
        else:
            if log_missing and target not in _missing_columns_warned:
                logger.warning(
                    "No source column found for team_info_common.%s among %s "
                    "(actual TeamYearByYearStats columns: %s) — inserting NULL",
                    target, candidates, list(history_df.columns),
                )
                _missing_columns_warned.add(target)
        stats[target] = value
    return stats


def insert_row(conn: sqlite3.Connection, team_id: str, season_str: str, identity: dict, stats: dict) -> None:
    row = {
        "team_id": team_id,
        "season_year": season_str,
        "league_id": LEAGUE_ID,
        "season_id": season_str_to_season_id(season_str),
        **identity,
        **stats,
    }
    columns = list(row.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    conn.execute(
        f"INSERT INTO team_info_common ({column_list}) VALUES ({placeholders})",
        [row[c] for c in columns],
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)

    needed = get_needed_team_seasons(conn)
    valid_team_ids = get_valid_team_ids()
    defunct_team_ids = {team_id for team_id, _ in needed if team_id not in valid_team_ids}
    if defunct_team_ids:
        logger.info(
            "Excluding %d team_id(s) not recognized as current NBA franchises — no "
            "live-API history available for these (defunct early-era teams): %s",
            len(defunct_team_ids), sorted(defunct_team_ids),
        )
        needed = {(team_id, season_str) for team_id, season_str in needed if team_id in valid_team_ids}

    existing = get_existing_team_seasons(conn)
    to_fetch_by_team = group_by_team(needed - existing)

    team_ids = sorted(to_fetch_by_team)
    if TEST_LIMIT is not None:
        team_ids = team_ids[:TEST_LIMIT]

    missing_seasons_total = sum(len(v) for v in to_fetch_by_team.values())
    logger.info(
        "%d team-season rows needed, %d already present, %d missing across %d team(s) to fetch this run",
        len(needed), len(existing), missing_seasons_total, len(team_ids),
    )

    for i, team_id in enumerate(team_ids, start=1):
        season_strs = sorted(to_fetch_by_team[team_id])
        logger.info("[%d/%d] team_id=%s — fetching %d missing season(s)", i, len(team_ids), team_id, len(season_strs))

        try:
            identity = fetch_team_identity(team_id)
            time.sleep(REQUEST_DELAY_SECONDS)
            history_df = fetch_team_history(team_id)
            if TEST_LIMIT is not None:
                logger.info("TeamYearByYearStats columns: %s", list(history_df.columns))
        except Exception as e:
            logger.error("Failed to fetch team_id=%s: %s", team_id, e)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        for season_str in season_strs:
            stats = extract_season_stats(history_df, season_str, log_missing=(i == 1))
            if not stats:
                logger.warning(
                    "No TeamYearByYearStats row for team_id=%s season=%s — skipping (likely a season "
                    "this endpoint doesn't carry, e.g. the still-in-progress current season)",
                    team_id, season_str,
                )
                continue
            try:
                insert_row(conn, team_id, season_str, identity, stats)
            except Exception as e:
                logger.error("Failed to insert team_id=%s season=%s: %s", team_id, season_str, e)

        time.sleep(REQUEST_DELAY_SECONDS)

    conn.close()


if __name__ == "__main__":
    main()