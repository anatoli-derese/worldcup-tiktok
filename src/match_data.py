"""Fetch World Cup match data from football-data.org."""
import requests
from dataclasses import dataclass, field
from src.config import FOOTBALL_DATA_API_KEY
from src.utils import get_logger, retry

logger = get_logger(__name__)

BASE_URL = "https://api.football-data.org/v4"
WORLD_CUP_ID = 2000  # verify at football-data.org


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


def _headers() -> dict:
    return {"X-Auth-Token": FOOTBALL_DATA_API_KEY}


@retry(max_attempts=3, delay=2)
def fetch_todays_matches() -> list[MatchInfo]:
    """Fetch finished matches from the World Cup competition."""
    if not FOOTBALL_DATA_API_KEY:
        logger.warning("No FOOTBALL_DATA_API_KEY set — returning empty list")
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/competitions/{WORLD_CUP_ID}/matches",
            headers=_headers(),
            params={"status": "FINISHED"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        matches = []
        for m in data.get("matches", []):
            match = MatchInfo(
                id=str(m.get("id", "")),
                home_team=m.get("homeTeam", {}).get("name", "Unknown"),
                away_team=m.get("awayTeam", {}).get("name", "Unknown"),
                home_score=m.get("score", {}).get("fullTime", {}).get("home"),
                away_score=m.get("score", {}).get("fullTime", {}).get("away"),
                status=m.get("status", "SCHEDULED"),
                utc_date=m.get("utcDate", ""),
                events=_parse_events(m),
            )
            matches.append(match)

        logger.info(f"Fetched {len(matches)} finished matches")
        return matches

    except requests.RequestException as e:
        logger.error(f"Failed to fetch matches: {e}")
        return []


def _parse_events(match: dict) -> list[str]:
    """Extract goal/card events from match data."""
    events = []
    for ev in match.get("goals", []):
        player = ev.get("scorer", {}).get("name", "Unknown")
        minute = ev.get("minute", "?")
        team = ev.get("team", {}).get("name", "")
        events.append(f"Goal: {player} ({team}) {minute}'")
    return events
