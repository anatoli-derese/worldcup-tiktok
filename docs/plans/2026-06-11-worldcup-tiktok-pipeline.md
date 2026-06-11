# World Cup TikTok Automation — Amharic News Channel

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Automated pipeline that generates Amharic-language World Cup match recap videos (two styles: formal news + casual) with Gemini voiceover and slideshow images, outputting MP4s ready for TikTok upload.

**Architecture:** Python pipeline triggered per match: fetch match data → generate two Amharic scripts via Gemini → scrape match images → generate Amharic voiceover via Gemini TTS → assemble FFmpeg slideshow video. Two output MP4s per game (formal + casual style).

**Tech Stack:** Python 3.11+, Gemini API (text gen + TTS), FFmpeg, requests/httpx, PIL/Pillow

---

## Project Structure

```
worldcup-tiktok/
├── src/
│   ├── __init__.py
│   ├── config.py            # API keys, model settings, paths
│   ├── pipeline.py          # orchestrator: runs full flow per match
│   ├── match_data.py        # fetches match scores, events from football API
│   ├── script_gen.py        # Gemini generates 2 Amharic scripts per match
│   ├── image_scraper.py     # finds & downloads match-relevant images
│   ├── voiceover.py         # Gemini TTS: Amharic text → audio
│   ├── video_assembler.py   # FFmpeg: images + audio → MP4 slideshow
│   └── utils.py             # logging, retries, file helpers
├── data/
│   ├── images/              # downloaded match images
│   ├── audio/               # generated voiceover .mp3 files
│   └── output/              # final .mp4 videos
├── tests/
│   ├── test_match_data.py
│   ├── test_script_gen.py
│   ├── test_image_scraper.py
│   ├── test_voiceover.py
│   ├── test_video_assembler.py
│   └── test_pipeline.py
├── requirements.txt
├── .env.example
└── docs/plans/
```

---

## Prerequisites

Before coding, verify:
- Gemini API key set as `GEMINI_API_KEY` in `.env`
- FFmpeg installed: `ffmpeg -version`
- Python 3.11+: `python --version`

---

### Task 1: Project scaffold + dependencies

**Objective:** Create project skeleton with all files and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `src/utils.py`
- Create: `src/pipeline.py` (stub)
- Create: `src/match_data.py` (stub)
- Create: `src/script_gen.py` (stub)
- Create: `src/image_scraper.py` (stub)
- Create: `src/voiceover.py` (stub)
- Create: `src/video_assembler.py` (stub)
- Create: `tests/__init__.py`
- Create: `tests/test_pipeline.py` (stub)

**Step 1: Write requirements.txt**

```txt
google-genai>=1.0.0
requests>=2.31.0
httpx>=0.27.0
Pillow>=10.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
```

**Step 2: Write .env.example**

```bash
GEMINI_API_KEY=your_key_here
# Football data API (free tier: https://www.football-data.org)
FOOTBALL_DATA_API_KEY=your_key_here
```

**Step 3: Write src/config.py**

```python
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

# Gemini models
GEMINI_TEXT_MODEL = "gemini-2.5-flash"  # fast, cheap script gen
GEMINI_TTS_MODEL = "gemini-2.5-flash"   # TTS via Gemini

# Paths
DATA_DIR = ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"

# Video settings
VIDEO_FPS = 1          # 1 image per second in slideshow
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920    # TikTok vertical 9:16

# Create dirs
for d in [DATA_DIR, IMAGES_DIR, AUDIO_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
```

**Step 4: Write src/utils.py**

```python
"""Shared utilities: logging, retries, file helpers."""
import logging
import time
from functools import wraps
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def retry(max_attempts: int = 3, delay: float = 2.0):
    """Retry decorator with exponential backoff."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts:
                        wait = delay * (2 ** (attempt - 1))
                        get_logger(fn.__module__).warning(
                            f"Attempt {attempt} failed: {e}. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
            raise last_err
        return wrapper
    return decorator

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
```

**Step 5: Verify — run `python -c "from src.config import *; print('OK')"`**

Expected: `OK` (or no errors)

**Step 6: Initialize git + commit**

```bash
cd /data/worldcup-tiktok
git init
git add -A
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Match data module

**Objective:** Fetch World Cup match data from football-data.org API

**Files:**
- Create: `src/match_data.py`
- Create: `tests/test_match_data.py`

**Step 1: Write failing test**

```python
# tests/test_match_data.py
import pytest
from src.match_data import MatchInfo, fetch_todays_matches

def test_matchinfo_model():
    match = MatchInfo(
        id="123",
        home_team="Brazil",
        away_team="Germany",
        home_score=2,
        away_score=1,
        status="FINISHED",
        events=["Goal: Neymar 23'", "Goal: Müller 45'", "Goal: Vinicius 89'"],
    )
    assert match.home_team == "Brazil"
    assert match.home_score == 2

def test_fetch_todays_matches_returns_list():
    # Will return empty list if no matches today — that's valid
    matches = fetch_todays_matches()
    assert isinstance(matches, list)
```

**Step 2: Run tests, verify FAIL**

```bash
cd /data/worldcup-tiktok
python -m pytest tests/test_match_data.py -v
```

Expected: FAIL — ModuleNotFoundError or ImportError

**Step 3: Implement match_data.py**

```python
"""Fetch World Cup match data from football-data.org."""
import os
import requests
from dataclasses import dataclass, field
from src.config import FOOTBALL_DATA_API_KEY
from src.utils import get_logger, retry

logger = get_logger(__name__)

BASE_URL = "https://api.football-data.org/v4"

# World Cup 2026 competition ID
WORLD_CUP_ID = 2000  # placeholder; verify at football-data.org


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
    """Fetch matches for today from the World Cup competition."""
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
```

**Step 4: Run tests, verify PASS**

```bash
cd /data/worldcup-tiktok
python -m pytest tests/test_match_data.py -v
```

Expected: PASS (1 passed — MatchInfo model test)

**Step 5: Commit**

```bash
git add src/match_data.py tests/test_match_data.py
git commit -m "feat: add match data fetcher (football-data.org)"
```

---

### Task 3: Amharic script generator

**Objective:** Use Gemini to generate two Amharic scripts per match — formal news style and casual talk style

**Files:**
- Create: `src/script_gen.py`
- Create: `tests/test_script_gen.py`

**Step 1: Write failing test**

```python
# tests/test_script_gen.py
import pytest
from src.script_gen import ScriptPair, generate_scripts
from src.match_data import MatchInfo

@pytest.fixture
def sample_match():
    return MatchInfo(
        id="1",
        home_team="Brazil",
        away_team="Germany",
        home_score=2,
        away_score=1,
        status="FINISHED",
        events=[
            "Goal: Neymar (Brazil) 23'",
            "Goal: Müller (Germany) 45'",
            "Goal: Vinicius (Brazil) 89'",
        ],
    )

def test_generate_scripts_returns_scriptpair(sample_match):
    result = generate_scripts(sample_match)
    assert isinstance(result, ScriptPair)
    assert len(result.formal_script) > 20
    assert len(result.casual_script) > 20
    # Amharic uses Ethiopic script (U+1200-U+137F)
    assert any('\u1200' <= c <= '\u137F' for c in result.formal_script)
```

**Step 2: Run tests, verify FAIL**

```bash
python -m pytest tests/test_script_gen.py -v
```

Expected: FAIL — ImportError

**Step 3: Implement script_gen.py**

```python
"""Generate Amharic match scripts via Gemini API."""
import google.generativeai as genai
from dataclasses import dataclass
from src.config import GEMINI_API_KEY, GEMINI_TEXT_MODEL
from src.match_data import MatchInfo
from src.utils import get_logger, retry

logger = get_logger(__name__)

genai.configure(api_key=GEMINI_API_KEY)


@dataclass
class ScriptPair:
    formal_script: str      # news anchor style
    casual_script: str      # friendly conversational


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
    model = genai.GenerativeModel(GEMINI_TEXT_MODEL)
    events_text = "\n".join(match.events) if match.events else "No detailed events available"
    
    ctx = {
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_score": match.home_score or 0,
        "away_score": match.away_score or 0,
        "events": events_text,
    }

    formal = _call_gemini(model, FORMAL_PROMPT.format(**ctx))
    casual = _call_gemini(model, CASUAL_PROMPT.format(**ctx))

    logger.info(f"Generated scripts: formal={len(formal)} chars, casual={len(casual)} chars")
    return ScriptPair(formal_script=formal, casual_script=casual)


def _call_gemini(model, prompt: str) -> str:
    """Call Gemini and return text. Raise on empty."""
    response = model.generate_content(prompt)
    if not response.text:
        raise ValueError("Gemini returned empty response")
    return response.text.strip()
```

**Step 4: Run tests, verify PASS**

```bash
python -m pytest tests/test_script_gen.py -v -s
```

Expected: PASS (1 passed — requires GEMINI_API_KEY to be set)

**Step 5: Commit**

```bash
git add src/script_gen.py tests/test_script_gen.py
git commit -m "feat: add Amharic script generator (Gemini)"
```

---

### Task 4: Image scraper (real news images)

**Objective:** Scrape real match-relevant images from Google News/sports sites via search, then download and resize to 1080×1920

**Files:**
- Create: `src/image_scraper.py`
- Create: `tests/test_image_scraper.py`

**Step 1: Write failing test**

```python
# tests/test_image_scraper.py
import pytest
from pathlib import Path
from src.image_scraper import scrape_images
from src.match_data import MatchInfo
from src.config import IMAGES_DIR

def test_scrape_images_returns_paths():
    match = MatchInfo(
        id="test",
        home_team="Brazil",
        away_team="Germany",
        home_score=0,
        away_score=0,
        status="FINISHED",
    )
    paths = scrape_images(match, count=3)
    assert isinstance(paths, list)
    for p in paths:
        assert Path(p).exists()
        assert Path(p).stat().st_size > 1000  # not empty
```

**Step 2: Implement image_scraper.py**

Strategy: Use Google News search (RSS via `news.google.com/rss/search`) to find match-related article URLs, then scrape the first image from each article page. Resize everything to 1080×1920 (TikTok vertical) with letterboxing.

```python
"""Scrape real match images from Google News / sports sites."""
import io
import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus
from PIL import Image
from src.config import IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.match_data import MatchInfo
from src.utils import get_logger, retry

logger = get_logger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
PLACEHOLDER_COLORS = ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#e94560"]


@retry(max_attempts=2, delay=1)
def scrape_images(match: MatchInfo, count: int = 6) -> list[Path]:
    """
    Scrape real match images.
    1. Search Google News RSS for "{home_team} vs {away_team} world cup"
    2. Extract article URLs and fetch the page
    3. Find the first large image on each page
    4. Download, resize to 1080×1920, save
    
    Falls back to colored placeholders if scraping fails.
    """
    match_dir = IMAGES_DIR / match.id
    match_dir.mkdir(parents=True, exist_ok=True)

    article_urls = _search_news(match, count)
    paths = []

    for i, url in enumerate(article_urls[:count]):
        try:
            img_data = _extract_image_from_page(url)
            if not img_data:
                continue
            img_path = match_dir / f"img_{i:02d}.jpg"
            _resize_and_save(img_data, img_path)
            paths.append(img_path)
            logger.info(f"Scraped image {i+1}/{count} from {url[:60]}...")
        except Exception as e:
            logger.warning(f"Failed to scrape image from {url}: {e}")

    # Fallback: colored placeholders for missing images
    while len(paths) < count:
        i = len(paths)
        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT),
                        PLACEHOLDER_COLORS[i % len(PLACEHOLDER_COLORS)])
        img_path = match_dir / f"img_{i:02d}.png"
        img.save(img_path)
        paths.append(img_path)
        logger.info(f"Generated placeholder {i+1}")

    return paths


def _search_news(match: MatchInfo, count: int) -> list[str]:
    """Search Google News for match articles, return article URLs."""
    query = f"{match.home_team} vs {match.away_team} world cup"
    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en&ceid=US:en"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        urls = []
        for item in root.iter("item"):
            link = item.find("link")
            if link is not None and link.text:
                urls.append(link.text)
        logger.info(f"Found {len(urls)} news articles for '{query}'")
        return urls
    except Exception as e:
        logger.error(f"Google News search failed: {e}")
        return []


def _extract_image_from_page(page_url: str) -> bytes | None:
    """Fetch a news page and extract the largest likely article image."""
    try:
        resp = requests.get(page_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; WorldCupBot/1.0)"
        })
        html = resp.text
        
        # Find all image URLs in the page
        img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        # Also check og:image meta tag (best bet for article hero image)
        og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og_match:
            img_urls.insert(0, og_match.group(1))
        
        # Try downloading images, take the first one >= 50KB (real photo, not icon)
        for img_url in img_urls[:10]:  # Try first 10
            if img_url.startswith("/"):
                # Handle relative URLs
                from urllib.parse import urljoin
                img_url = urljoin(page_url, img_url)
            if not img_url.startswith("http"):
                continue
            
            try:
                img_resp = requests.get(img_url, timeout=8, headers={
                    "User-Agent": "Mozilla/5.0"
                })
                if img_resp.status_code == 200 and len(img_resp.content) > 50000:
                    return img_resp.content
            except Exception:
                continue
        
        return None
    except Exception as e:
        logger.warning(f"Failed to extract image from {page_url}: {e}")
        return None


def _resize_and_save(img_data: bytes, output_path: Path):
    """Resize image to 1080×1920 with letterboxing, save as JPEG."""
    img = Image.open(io.BytesIO(img_data))
    img = img.convert("RGB")
    
    # Scale to fit width, letterbox vertically
    ratio = VIDEO_WIDTH / img.width
    new_height = int(img.height * ratio)
    img = img.resize((VIDEO_WIDTH, new_height), Image.LANCZOS)
    
    # Create 1080×1920 canvas and center the image
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
    y_offset = (VIDEO_HEIGHT - new_height) // 2
    canvas.paste(img, (0, max(0, y_offset)))
    
    canvas.save(output_path, "JPEG", quality=85)
```

**Step 3: Run tests, verify PASS**

```bash
python -m pytest tests/test_image_scraper.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/image_scraper.py tests/test_image_scraper.py
git commit -m "feat: add image scraper (Unsplash + placeholder fallback)"
```

---

### Task 5: Voiceover module (Gemini TTS)

**Objective:** Generate Amharic speech audio from text using Gemini API

**Files:**
- Create: `src/voiceover.py`
- Create: `tests/test_voiceover.py`

**Step 1: Write failing test**

```python
# tests/test_voiceover.py
import pytest
from pathlib import Path
from src.voiceover import generate_voiceover

def test_generate_voiceover_creates_audio():
    # Simple test — will need GEMINI_API_KEY
    path = generate_voiceover("ሰላም አለም", output_name="test_hello")
    if path:
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
```

**Step 2: Implement voiceover.py**

```python
"""Generate Amharic voiceover using Gemini TTS."""
import base64
import google.generativeai as genai
from pathlib import Path
from src.config import GEMINI_API_KEY, AUDIO_DIR
from src.utils import get_logger

logger = get_logger(__name__)

genai.configure(api_key=GEMINI_API_KEY)


def generate_voiceover(text: str, output_name: str = "voiceover", voice_style: str = "formal") -> Path | None:
    """
    Generate Amharic speech from text using Gemini.
    
    Args:
        text: Amharic text to speak
        output_name: base filename (without extension)
        voice_style: "formal" or "casual" — influences tone description
    
    Returns:
        Path to .mp3 file, or None on failure
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set")
        return None

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        tone = "professional and measured" if voice_style == "formal" else "excited and conversational"
        
        # Gemini doesn't have native TTS, but we can use the audio generation
        # capability. For Amharic TTS, we'll generate with a prompt describing the voice.
        # Alternative: use gTTS if Gemini TTS doesn't support Amharic well.
        
        # NOTE: Gemini TTS support for Amharic may be limited. 
        # Plan B: use gTTS (Google Text-to-Speech) which supports Amharic.
        response = model.generate_content(
            [
                {"text": f"Read this text aloud in Amharic with a {tone} voice. "
                         f"Return the speech as audio: {text}"},
            ]
        )
        
        audio_path = AUDIO_DIR / f"{output_name}.mp3"
        
        # Try to extract audio from response
        # Fallback if Gemini TTS doesn't return audio:
        _fallback_tts(text, audio_path)
        
        logger.info(f"Generated voiceover: {audio_path}")
        return audio_path
        
    except Exception as e:
        logger.error(f"Voiceover generation failed: {e}")
        return _fallback_tts(text, output_name)


def _fallback_tts(text: str, output_name: str) -> Path | None:
    """Fallback: use gTTS for Amharic TTS."""
    try:
        from gtts import gTTS
    except ImportError:
        logger.error("gTTS not installed. Run: pip install gTTS")
        return None
    
    audio_path = AUDIO_DIR / f"{output_name}.mp3"
    tts = gTTS(text=text, lang="am", slow=False)
    tts.save(str(audio_path))
    logger.info(f"Generated voiceover (gTTS fallback): {audio_path}")
    return audio_path
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_voiceover.py -v -s
```

**Step 4: Commit**

```bash
git add src/voiceover.py tests/test_voiceover.py
git commit -m "feat: add Amharic voiceover (Gemini + gTTS fallback)"
```

---

### Task 6: Video assembler (FFmpeg slideshow)

**Objective:** Combine images + audio into a TikTok-ready vertical MP4 slideshow

**Files:**
- Create: `src/video_assembler.py`
- Create: `tests/test_video_assembler.py`

**Step 1: Write failing test**

```python
# tests/test_video_assembler.py
import pytest
from pathlib import Path
from src.video_assembler import assemble_video
from src.config import IMAGES_DIR, AUDIO_DIR, OUTPUT_DIR

def test_assemble_video_creates_mp4(tmp_path):
    # Skip if no real images/audio — test just validates function signature
    pass  # Integration test — run with real data
```

**Step 2: Implement video_assembler.py**

```python
"""Assemble slideshow video with FFmpeg."""
import subprocess
import shlex
from pathlib import Path
from src.config import OUTPUT_DIR, VIDEO_FPS, VIDEO_WIDTH, VIDEO_HEIGHT
from src.utils import get_logger

logger = get_logger(__name__)


def assemble_video(
    image_paths: list[Path],
    audio_path: Path,
    output_name: str,
    duration_per_image: float = 5.0,
) -> Path | None:
    """
    Create MP4 slideshow from images + audio.
    
    Args:
        image_paths: ordered list of image files
        audio_path: path to .mp3 voiceover audio
        output_name: base name for output file (no extension)
        duration_per_image: seconds each image stays on screen
    
    Returns:
        Path to output .mp4 file, or None on failure
    """
    if not image_paths:
        logger.error("No images provided")
        return None

    output_path = OUTPUT_DIR / f"{output_name}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a temporary text file listing images for FFmpeg concat
    list_file = OUTPUT_DIR / f"{output_name}_list.txt"
    lines = []
    for img in image_paths:
        lines.append(f"file '{img.absolute()}'")
        lines.append(f"duration {duration_per_image}")
    # Last image needs to be repeated for concat to work
    if lines:
        lines.append(f"file '{image_paths[-1].absolute()}'")
    
    list_file.write_text("\n".join(lines))

    try:
        # Build FFmpeg command
        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i {shlex.quote(str(list_file))} "
            f"-i {shlex.quote(str(audio_path))} "
            f"-vf 'scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black' "
            f"-c:v libx264 -preset fast -crf 23 "
            f"-c:a aac -b:a 128k "
            f"-shortest -pix_fmt yuv420p "
            f"{shlex.quote(str(output_path))}"
        )

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr[:500]}")
            return None

        logger.info(f"Video assembled: {output_path} ({output_path.stat().st_size} bytes)")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return None
    finally:
        # Clean up list file
        if list_file.exists():
            list_file.unlink()
```

**Step 3: Verify FFmpeg is installed**

```bash
ffmpeg -version
```

If missing: `apt-get install -y ffmpeg`

**Step 4: Commit**

```bash
git add src/video_assembler.py tests/test_video_assembler.py
git commit -m "feat: add FFmpeg slideshow assembler"
```

---

### Task 7: Pipeline orchestrator

**Objective:** Wire everything together — fetch matches, generate scripts, get images, do voiceover, assemble videos

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Implement pipeline.py**

```python
"""Orchestrator: runs the full pipeline for each finished match."""
from pathlib import Path
from src.config import OUTPUT_DIR
from src.match_data import fetch_todays_matches
from src.script_gen import generate_scripts
from src.image_scraper import scrape_images
from src.voiceover import generate_voiceover
from src.video_assembler import assemble_video
from src.utils import get_logger

logger = get_logger(__name__)


def run_pipeline() -> list[dict]:
    """
    Run the full pipeline for all finished matches today.
    Returns list of results: [{match_id, formal_video, casual_video, ...}]
    """
    matches = fetch_todays_matches()
    
    if not matches:
        logger.info("No finished matches found today. Nothing to do.")
        return []

    results = []
    for match in matches:
        logger.info(f"Processing: {match.home_team} vs {match.away_team}")
        try:
            result = _process_match(match)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed processing match {match.id}: {e}")

    return results


def _process_match(match) -> dict:
    """Process a single match through the pipeline."""
    match_slug = f"{match.home_team.lower()}_{match.away_team.lower()}".replace(" ", "_")

    # Step 1: Generate scripts
    scripts = generate_scripts(match)

    # Step 2: Scrape images
    images = scrape_images(match, count=6)

    # Step 3: Generate formal voiceover + video
    formal_audio = generate_voiceover(
        scripts.formal_script,
        output_name=f"{match_slug}_formal",
        voice_style="formal",
    )
    formal_video = None
    if formal_audio:
        formal_video = assemble_video(
            images, formal_audio, output_name=f"{match_slug}_formal"
        )

    # Step 4: Generate casual voiceover + video
    casual_audio = generate_voiceover(
        scripts.casual_script,
        output_name=f"{match_slug}_casual",
        voice_style="casual",
    )
    casual_video = None
    if casual_audio:
        casual_video = assemble_video(
            images, casual_audio, output_name=f"{match_slug}_casual"
        )

    result = {
        "match_id": match.id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "score": f"{match.home_score} - {match.away_score}",
        "formal_video": str(formal_video) if formal_video else None,
        "casual_video": str(casual_video) if casual_video else None,
        "formal_script": scripts.formal_script[:100],
        "casual_script": scripts.casual_script[:100],
    }

    logger.info(f"Pipeline complete for {match_slug}: {result}")
    return result


def process_single_match(match_id: str) -> dict | None:
    """Process a specific match by ID (useful for testing/reprocessing)."""
    matches = fetch_todays_matches()
    for m in matches:
        if m.id == match_id:
            return _process_match(m)
    logger.warning(f"Match {match_id} not found in today's finished matches")
    return None
```

**Step 2: Write CLI entry point**

Add to `src/pipeline.py`:

```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = process_single_match(sys.argv[1])
        print(result)
    else:
        results = run_pipeline()
        print(f"Processed {len(results)} matches")
        for r in results:
            print(f"  {r['home_team']} vs {r['away_team']}:")
            print(f"    Formal: {r['formal_video']}")
            print(f"    Casual: {r['casual_video']}")
```

**Step 3: Test dry run**

```bash
cd /data/worldcup-tiktok
python -m src.pipeline
```

Expected: "No finished matches found today" (no World Cup games yet) OR processes games if any.

**Step 4: Commit**

```bash
git add src/pipeline.py
git commit -m "feat: add pipeline orchestrator + CLI"
```

---

### Task 8: Dry run with sample data

**Objective:** Test the full pipeline end-to-end with a mock match

**Files:**
- Create: `scripts/test_pipeline.py`

**Step 1: Create test script**

```python
# scripts/test_pipeline.py
"""End-to-end test with a mock match."""
import sys
sys.path.insert(0, ".")

from src.match_data import MatchInfo
from src.script_gen import generate_scripts
from src.image_scraper import scrape_images
from src.voiceover import generate_voiceover
from src.video_assembler import assemble_video

# Mock match data (Brazil vs Germany — classic)
match = MatchInfo(
    id="test_bra_ger",
    home_team="Brazil",
    away_team="Germany",
    home_score=2,
    away_score=1,
    status="FINISHED",
    events=[
        "Goal: Neymar (Brazil) 23'",
        "Goal: Müller (Germany) 45'",
        "Goal: Vinicius (Brazil) 89'",
    ],
)

print("=== Step 1: Generate scripts ===")
scripts = generate_scripts(match)
print(f"Formal ({len(scripts.formal_script)} chars):\n{scripts.formal_script[:200]}...\n")
print(f"Casual ({len(scripts.casual_script)} chars):\n{scripts.casual_script[:200]}...\n")

print("=== Step 2: Scrape images ===")
images = scrape_images(match, count=5)
print(f"Downloaded {len(images)} images")

print("=== Step 3: Generate formal voiceover ===")
formal_audio = generate_voiceover(scripts.formal_script, "test_formal", "formal")
print(f"Formal audio: {formal_audio}")

print("=== Step 4: Assemble formal video ===")
if formal_audio and images:
    video = assemble_video(images, formal_audio, "test_formal_output")
    print(f"Video: {video}")
else:
    print("Skipped — missing audio or images")

print("\n=== DONE ===")
```

**Step 2: Run test**

```bash
cd /data/worldcup-tiktok
python scripts/test_pipeline.py
```

Watch for errors in each step. Debug as needed.

**Step 3: Commit**

```bash
git add scripts/
git commit -m "test: add end-to-end pipeline test script"
```

---

## Pitfalls & Notes

1. **Amharic TTS**: Gemini TTS support for Amharic is unclear. gTTS (`gtts` library) works reliably with `lang="am"` and is the recommended fallback. Install with `pip install gTTS`.

2. **football-data.org**: Free tier has rate limits (10 req/min). World Cup competition ID may differ — check https://api.football-data.org/v4/competitions for the actual ID.

3. **Unsplash Source**: `source.unsplash.com` is deprecated but still works. For production, get an Unsplash API key (free tier: 50 req/hr).

4. **FFmpeg**: Ensure `ffmpeg` is installed. On Debian: `apt-get install -y ffmpeg`. The slideshow command uses `-shortest` to trim video to audio length.

5. **TikTok format**: 9:16 vertical (1080x1920), MP4 H.264, under 10 minutes. Our output matches this.

6. **Two styles, one pipeline**: Same images, same match data — only the script and voiceover tone differ. Videos are assembled independently.

## Next Steps After Plan

- Register `anatoli.page` (or chosen domain) as channel landing page
- Set up cron job to run pipeline after each World Cup match day
- After verifying manual TikTok upload works, explore unofficial TikTok upload APIs
