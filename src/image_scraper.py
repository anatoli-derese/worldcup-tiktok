"""Image pipeline — real match photos (Startpage/Flickr/BBC) + generated cards fallback."""
import io
from pathlib import Path
from PIL import Image
from src.config import IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.match_data import MatchInfo
from src.football_scraper import scrape_match_images
from src.utils import get_logger

logger = get_logger(__name__)


def scrape_images(match: MatchInfo, count: int = 6) -> list[Path]:
    match_dir = IMAGES_DIR / match.id
    match_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    try:
        images = scrape_match_images(match.home_team, match.away_team, count=count)
        for i, (img, source) in enumerate(images):
            img_path = match_dir / f"img_{i:02d}.jpg"
            _resize_save(img, img_path)
            paths.append(img_path)
            logger.info(f"[{source}] {img.size[0]}x{img.size[1]}")
    except Exception as e:
        logger.error(f"Scraper failed: {e}")

    return paths


def _resize_save(img: Image.Image, output_path: Path):
    img = img.convert("RGB")
    ratio = VIDEO_WIDTH / img.width
    new_h = int(img.height * ratio)
    img = img.resize((VIDEO_WIDTH, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0))
    canvas.paste(img, (0, max(0, (VIDEO_HEIGHT - new_h) // 2)))
    canvas.save(output_path, "JPEG", quality=85)
