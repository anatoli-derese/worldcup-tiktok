"""Generate Amharic voiceover using gTTS with Gemini TTS fallback."""
from pathlib import Path
from src.config import GEMINI_API_KEY, AUDIO_DIR
from src.utils import get_logger

logger = get_logger(__name__)


def generate_voiceover(text: str, output_name: str = "voiceover", voice_style: str = "formal") -> Path | None:
    """Generate Amharic speech: gTTS primary, Gemini fallback."""
    return _gtts_speak(text, output_name) or _gemini_speak(text, output_name, voice_style)


def _gtts_speak(text: str, output_name: str) -> Path | None:
    try:
        from gtts import gTTS
    except ImportError:
        logger.error("gTTS not installed. Run: pip install gTTS")
        return None

    audio_path = AUDIO_DIR / f"{output_name}.mp3"
    try:
        gTTS(text=text, lang="am", slow=False).save(str(audio_path))
        logger.info(f"Voiceover (gTTS): {audio_path} ({audio_path.stat().st_size} bytes)")
        return audio_path
    except Exception as e:
        logger.error(f"gTTS failed: {e}")
        return None


def _gemini_speak(text: str, output_name: str, voice_style: str) -> Path | None:
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai

        tone = "professional and measured" if voice_style == "formal" else "excited and conversational"
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Read in Amharic with {tone} voice. Return audio: {text}",
        )

        audio_path = AUDIO_DIR / f"{output_name}.mp3"
        if hasattr(response, 'candidates') and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    audio_path.write_bytes(part.inline_data.data)
                    logger.info(f"Voiceover (Gemini): {audio_path}")
                    return audio_path

        logger.warning("Gemini returned no audio data")
        return None
    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")
        return None
