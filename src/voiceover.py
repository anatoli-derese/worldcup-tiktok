"""Generate Amharic voiceover using gTTS with Gemini TTS as optional fallback."""
from pathlib import Path
from src.config import GEMINI_API_KEY, AUDIO_DIR
from src.utils import get_logger

logger = get_logger(__name__)


def generate_voiceover(
    text: str, output_name: str = "voiceover", voice_style: str = "formal"
) -> Path | None:
    """
    Generate Amharic speech from text.
    Primary: gTTS (reliable Amharic support via lang='am')
    Fallback: Gemini TTS (may not support Amharic)

    Args:
        text: Amharic text to speak
        output_name: base filename (without extension)
        voice_style: "formal" or "casual" — only affects speed/tone if using Gemini

    Returns:
        Path to .mp3 file, or None on failure
    """
    # Try gTTS first — best Amharic support
    result = _gtts_speak(text, output_name)
    if result:
        return result

    # Fallback: try Gemini
    result = _gemini_speak(text, output_name, voice_style)
    if result:
        return result

    logger.error("All voiceover methods failed")
    return None


def _gtts_speak(text: str, output_name: str) -> Path | None:
    """Use gTTS for Amharic text-to-speech."""
    try:
        from gtts import gTTS
    except ImportError:
        logger.error("gTTS not installed. Run: pip install gTTS")
        return None

    audio_path = AUDIO_DIR / f"{output_name}.mp3"
    try:
        tts = gTTS(text=text, lang="am", slow=False)
        tts.save(str(audio_path))
        logger.info(f"Generated voiceover (gTTS): {audio_path} ({audio_path.stat().st_size} bytes)")
        return audio_path
    except Exception as e:
        logger.error(f"gTTS failed: {e}")
        return None


def _gemini_speak(text: str, output_name: str, voice_style: str) -> Path | None:
    """Use Gemini for TTS (may not support Amharic output)."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping Gemini TTS")
        return None

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        tone = "professional and measured" if voice_style == "formal" else "excited and conversational"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Read this text aloud in Amharic with a {tone} voice. Return speech as audio: {text}",
        )

        # Gemini audio responses come as inline data
        audio_path = AUDIO_DIR / f"{output_name}.mp3"

        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    audio_path.write_bytes(part.inline_data.data)
                    logger.info(f"Generated voiceover (Gemini): {audio_path}")
                    return audio_path

        logger.warning("Gemini response had no audio data")
        return None

    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")
        return None
