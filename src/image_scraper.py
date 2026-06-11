"""Scrape real match images from Google News / sports sites."""
import io
import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus, urljoin
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
        og_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html
        )
        if og_match:
            img_urls.insert(0, og_match.group(1))

        # Try downloading images, take the first one >= 50KB (real photo, not icon)
        for img_url in img_urls[:10]:  # Try first 10
            if img_url.startswith("/"):
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
    img = img.resize((VIDEO_WIDTH, new_height), Image.Resampling.LANCZOS)

    # Create 1080×1920 canvas and center the image
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
    y_offset = (VIDEO_HEIGHT - new_height) // 2
    canvas.paste(img, (0, max(0, y_offset)))

    canvas.save(output_path, "JPEG", quality=85)
