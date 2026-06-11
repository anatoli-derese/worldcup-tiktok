"""Generate Amharic match scripts via Gemini API."""
from google import genai
from google.genai import types
from dataclasses import dataclass
from src.config import GEMINI_API_KEY, GEMINI_TEXT_MODEL
from src.match_data import MatchInfo
from src.utils import get_logger, retry

logger = get_logger(__name__)

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


@dataclass
class ScriptPair:
    formal_script: str
    casual_script: str


FORMAL_PROMPT = """You are an Amharic sports news anchor. Write a short 60-90 second 
news segment in Amharic about this World Cup match. Be professional, factual, 
and engaging. Mention the final score, key goals, and standout players.

Match: {home_team} vs {away_team}
Score: {home_score} - {away_score}
Events: {events}

Write ONLY the Amharic script. No English. No stage directions. Keep it under 150 words."""

CASUAL_PROMPT = """You are a passionate Ethiopian football fan talking to friends. 
Write a short 60-90 second casual reaction in Amharic about this World Cup match. 
Be excited, use slang, react emotionally to the goals. Like you're recording a voice note.

Match: {home_team} vs {away_team}
Score: {home_score} - {away_score}
Events: {events}

Write ONLY the Amharic script. No English. No stage directions. Keep it under 150 words."""


@retry(max_attempts=3, delay=2)
def generate_scripts(match: MatchInfo) -> ScriptPair:
    """Generate formal and casual Amharic scripts for a match."""
    if not _client:
        logger.error("GEMINI_API_KEY not set")
        return ScriptPair(
            formal_script="የምርጥ ጨዋታ ነበር! (formal script unavailable)",
            casual_script="እሺ ሰዎች! ምን አይነት ጨዋታ ነበር! (casual script unavailable)",
        )

    events_text = "\n".join(match.events) if match.events else "No detailed events available"

    ctx = {
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_score": match.home_score or 0,
        "away_score": match.away_score or 0,
        "events": events_text,
    }

    formal = _call_gemini(FORMAL_PROMPT.format(**ctx))
    casual = _call_gemini(CASUAL_PROMPT.format(**ctx))

    logger.info(f"Generated scripts: formal={len(formal)} chars, casual={len(casual)} chars")
    return ScriptPair(formal_script=formal, casual_script=casual)


def _call_gemini(prompt: str) -> str:
    """Call Gemini and return text. Raise on empty response."""
    response = _client.models.generate_content(
        model=GEMINI_TEXT_MODEL,
        contents=prompt,
    )
    if not response.text:
        raise ValueError("Gemini returned empty response")
    return response.text.strip()
