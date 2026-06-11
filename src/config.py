"""Configuration loaded from environment."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
ROOT = Path(__file__).resolve().parent.parent

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")

GEMINI_TEXT_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash"

DATA_DIR = ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Create dirs
for d in [DATA_DIR, IMAGES_DIR, AUDIO_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
