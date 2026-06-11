"""Generate Amharic match scripts via Gemini API."""
from google import genai
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


PROMPT = {
    "formal": """You are an Amharic sports news anchor. Write a short 60-90 second 
news segment in Amharic about this World Cup match. Be professional, factual, 
and engaging. Mention the final score, key goals, and standout players.

Match: {home_team} vs {away_team}
Score: {home_score} - {away_score}
Events: {events}

Write ONLY the Amharic script. No English. No stage directions. Keep it under 150 words.""",
    "casual": """You are a passionate Ethiopian football fan talking to friends. 
Write a short 60-90 second casual reaction in Amharic about this World Cup match. 
Be excited, use slang, react emotionally to the goals. Like you're recording a voice note.

Match: {home_team} vs {away_team}
Score: {home_score} - {away_score}
Events: {events}

Write ONLY the Amharic script. No English. No stage directions. Keep it under 150 words.""",
}


@retry(max_attempts=3, delay=2)
def generate_scripts(match: MatchInfo) -> ScriptPair:
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

    formal = _call(PROMPT["formal"].format(**ctx))
    casual = _call(PROMPT["casual"].format(**ctx))
    logger.info(f"Scripts: formal={len(formal)} casual={len(casual)} chars")
    return ScriptPair(formal, casual)


def _call(prompt: str) -> str:
    resp = _client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=prompt)
    if not resp.text:
        raise ValueError("Gemini returned empty response")
    return resp.text.strip()
