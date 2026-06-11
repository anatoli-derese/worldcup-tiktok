"""Fetch World Cup match data from football-data.org."""
import requests
from dataclasses import dataclass, field
from src.config import FOOTBALL_DATA_API_KEY
from src.utils import get_logger, retry

logger = get_logger(__name__)
BASE_URL = "https://api.football-data.org/v4"
WORLD_CUP_ID = 2000


@dataclass
class MatchInfo:
    id: str
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    status: str = "SCHEDULED"  # SCHEDULED, LIVE, FINISHED
    events: list[str] = field(default_factory=list)
    utc_date: str = ""


@retry(max_attempts=3, delay=2)
def fetch_todays_matches() -> list[MatchInfo]:
    if not FOOTBALL_DATA_API_KEY:
        logger.warning("FOOTBALL_DATA_API_KEY not set")
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/competitions/{WORLD_CUP_ID}/matches",
            headers={"X-Auth-Token": FOOTBALL_DATA_API_KEY},
            params={"status": "FINISHED"},
            timeout=15,
        )
        resp.raise_for_status()
        return [_parse_match(m) for m in resp.json().get("matches", [])]

    except requests.RequestException as e:
        logger.error(f"Failed to fetch matches: {e}")
        return []


def _parse_match(m: dict) -> MatchInfo:
    return MatchInfo(
        id=str(m.get("id", "")),
        home_team=m.get("homeTeam", {}).get("name", "Unknown"),
        away_team=m.get("awayTeam", {}).get("name", "Unknown"),
        home_score=m.get("score", {}).get("fullTime", {}).get("home"),
        away_score=m.get("score", {}).get("fullTime", {}).get("away"),
        status=m.get("status", "SCHEDULED"),
        utc_date=m.get("utcDate", ""),
        events=_parse_events(m),
    )


def _parse_events(match: dict) -> list[str]:
    events = []
    for ev in match.get("goals", []):
        name = ev.get("scorer", {}).get("name", "Unknown")
        minute = ev.get("minute", "?")
        team = ev.get("team", {}).get("name", "")
        events.append(f"Goal: {name} ({team}) {minute}'")
    return events
