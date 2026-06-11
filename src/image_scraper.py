"""Scrape real match images from Google News / sports sites."""
import io, re, requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus, urljoin
from PIL import Image
from src.config import IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.match_data import MatchInfo
from src.utils import get_logger, retry

logger = get_logger(__name__)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
PLACEHOLDER = ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#e94560"]


@retry(max_attempts=2, delay=1)
def scrape_images(match: MatchInfo, count: int = 6) -> list[Path]:
    """Scrape match images from Google News → article pages → download → resize to 9:16."""
    match_dir = IMAGES_DIR / match.id
    match_dir.mkdir(parents=True, exist_ok=True)

    article_urls = _search_news(match)
    paths = []

    for i, url in enumerate(article_urls[:count]):
        try:
            img_data = _extract_image_from_page(url)
            if not img_data:
                continue
            img_path = match_dir / f"img_{i:02d}.jpg"
            _resize_and_save(img_data, img_path)
            paths.append(img_path)
        except Exception as e:
            logger.warning(f"Image scrape failed [{url[:60]}]: {e}")

    while len(paths) < count:
        i = len(paths)
        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), PLACEHOLDER[i % len(PLACEHOLDER)])
        img_path = match_dir / f"img_{i:02d}.png"
        img.save(img_path)
        paths.append(img_path)

    return paths


def _search_news(match: MatchInfo) -> list[str]:
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
    try:
        resp = requests.get(page_url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; WorldCupBot/1.0)"})
        html = resp.text
        img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og:
            img_urls.insert(0, og.group(1))

        for img_url in img_urls[:10]:
            if img_url.startswith("/"):
                img_url = urljoin(page_url, img_url)
            if not img_url.startswith("http"):
                continue
            try:
                r = requests.get(img_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.content) > 50000:
                    return r.content
            except Exception:
                continue
        return None
    except Exception as e:
        logger.warning(f"Image extract failed [{page_url[:60]}]: {e}")
        return None


def _resize_and_save(img_data: bytes, output_path: Path):
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    ratio = VIDEO_WIDTH / img.width
    new_h = int(img.height * ratio)
    img = img.resize((VIDEO_WIDTH, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
    canvas.paste(img, (0, max(0, (VIDEO_HEIGHT - new_h) // 2)))
    canvas.save(output_path, "JPEG", quality=85)
