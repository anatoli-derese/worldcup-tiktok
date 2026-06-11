"""Generate match card images for TikTok slideshows."""
import io
import re
import xml.etree.ElementTree as ET
import requests
from pathlib import Path
from urllib.parse import urljoin
from PIL import Image, ImageDraw, ImageFont
from src.config import IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.match_data import MatchInfo
from src.utils import get_logger, retry

logger = get_logger(__name__)

TEAM_COLORS = {
    "brazil": ("#009c3b", "#ffdf00"),
    "germany": ("#000000", "#dd0000"),
    "argentina": ("#75aadb", "#ffffff"),
    "france": ("#002395", "#ffffff"),
    "england": ("#ffffff", "#cf081f"),
    "spain": ("#c60b1e", "#ffc400"),
    "netherlands": ("#f36c21", "#ffffff"),
    "italy": ("#009246", "#ffffff"),
    "portugal": ("#006600", "#ff0000"),
    "belgium": ("#000000", "#fdda24"),
    "default": ("#1a1a2e", "#e94560"),
}


def scrape_images(match: MatchInfo, count: int = 6) -> list[Path]:
    """Get images: news scrape → generated match cards as fallback."""
    match_dir = IMAGES_DIR / match.id
    match_dir.mkdir(parents=True, exist_ok=True)

    paths = _scrape_news_fast(match, count, match_dir)
    needed = count - len(paths)
    if needed > 0:
        paths += _generate_cards(match, needed, match_dir, start_i=len(paths))
    return paths


def _scrape_news_fast(match: MatchInfo, count: int, match_dir: Path) -> list[Path]:
    """Quick news image attempt — returns whatever succeeds in 10s."""
    try:
        resp = requests.get(
            "https://news.google.com/rss/search",
            params={"q": f"{match.home_team} {match.away_team} world cup", "hl": "en", "ceid": "US:en"},
            timeout=8,
        )
        root = ET.fromstring(resp.text)
        urls = [item.find("link").text for item in root.iter("item") if item.find("link") is not None]
    except Exception:
        return []

    paths = []
    for url in urls[:min(count, 3)]:
        try:
            page = requests.get(url, timeout=8, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            og = re.search(r'og:image["\'][^>]+content=["\']([^"\']+)', page.text[:50000])
            img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', page.text[:100000], re.I)
            if og:
                img_urls.insert(0, og.group(1))

            for img_url in img_urls[:5]:
                if img_url.startswith("/"):
                    img_url = urljoin(page.url, img_url)
                if not img_url.startswith("http") or "logo" in img_url.lower() or "icon" in img_url.lower():
                    continue
                try:
                    r = requests.get(img_url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
                    if r.status_code == 200 and len(r.content) > 30000:
                        img_path = match_dir / f"img_{len(paths):02d}.jpg"
                        _resize_save(r.content, img_path)
                        paths.append(img_path)
                        logger.info(f"News image: {url[:50]}")
                        break
                except Exception:
                    continue
        except Exception:
            continue
    return paths


def _generate_cards(match: MatchInfo, count: int, match_dir: Path, start_i: int = 0) -> list[Path]:
    """Generate professional match card slides with team colors + score overlay."""
    home_color, home_accent = TEAM_COLORS.get(match.home_team.lower(), TEAM_COLORS["default"])
    away_color, away_accent = TEAM_COLORS.get(match.away_team.lower(), TEAM_COLORS["default"])

    cards = [
        _make_card(f"{match.home_team}\nVS\n{match.away_team}",
                   home_color, home_accent, "VS", match_dir, f"img_{start_i:02d}.png"),
        _make_card(f"FINAL SCORE\n{match.home_score or '?'} - {match.away_score or '?'}",
                   "#0f3460", "#e94560", "SCORE", match_dir, f"img_{start_i+1:02d}.png"),
    ]

    for idx, event in enumerate(match.events[:count - 2]):
        color, accent = (home_color, home_accent) if match.home_team in event else (away_color, away_accent)
        cards.append(_make_card(event, color, accent, "GOAL", match_dir, f"img_{start_i+2+idx:02d}.png"))

    return [c for c in cards if c]


def _make_card(text: str, bg: str, accent: str, label: str, match_dir: Path, filename: str) -> Path | None:
    """Create a 1080x1920 card with gradient background and centered text."""
    try:
        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), bg)
        draw = ImageDraw.Draw(img)

        # Accent bar at top
        draw.rectangle([(0, 0), (VIDEO_WIDTH, 8)], fill=accent)
        draw.rectangle([(0, VIDEO_HEIGHT - 8), (VIDEO_WIDTH, VIDEO_HEIGHT)], fill=accent)

        # Label tag
        draw.rectangle([(40, 60), (200, 110)], fill=accent)
        try:
            font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        except OSError:
            font_label = ImageFont.load_default()
            font_main = ImageFont.load_default()

        draw.text((60, 65), label, fill="#ffffff", font=font_label)

        # Main text centered
        lines = text.split("\n")
        y = 400
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_main)
            tw = bbox[2] - bbox[0]
            draw.text(((VIDEO_WIDTH - tw) // 2, y), line, fill="#ffffff", font=font_main)
            y += 120

        img_path = match_dir / filename
        img.save(img_path, "PNG")
        return img_path
    except Exception as e:
        logger.warning(f"Card generation failed: {e}")
        return None


def _resize_save(img_data: bytes, output_path: Path):
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    ratio = VIDEO_WIDTH / img.width
    new_h = int(img.height * ratio)
    img = img.resize((VIDEO_WIDTH, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
    canvas.paste(img, (0, max(0, (VIDEO_HEIGHT - new_h) // 2)))
    canvas.save(output_path, "JPEG", quality=85)
