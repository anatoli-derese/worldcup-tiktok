"""Orchestrator: runs the full pipeline for each finished match."""
from src.match_data import fetch_todays_matches
from src.script_gen import generate_scripts
from src.image_scraper import scrape_images
from src.voiceover import generate_voiceover
from src.video_assembler import assemble_video
from src.utils import get_logger

logger = get_logger(__name__)

_BROWSER_AVAILABLE = None  # lazily checked


def _tiktok_available() -> bool:
    global _BROWSER_AVAILABLE
    if _BROWSER_AVAILABLE is None:
        try:
            from src.tiktok_browser import is_configured
            _BROWSER_AVAILABLE = is_configured()
        except Exception:
            _BROWSER_AVAILABLE = False
    return _BROWSER_AVAILABLE


def run_pipeline() -> list[dict]:
    matches = fetch_todays_matches()
    if not matches:
        logger.info("No finished matches today.")
        return []

    results = []
    for match in matches:
        logger.info(f"Processing: {match.home_team} vs {match.away_team}")
        try:
            results.append(_process_match(match))
        except Exception as e:
            logger.error(f"Failed match {match.id}: {e}")
    return results


def _process_match(match) -> dict:
    slug = f"{match.home_team}_{match.away_team}".lower().replace(" ", "_").replace(".", "")

    logger.info(f"[{slug}] Generating scripts...")
    scripts = generate_scripts(match)

    logger.info(f"[{slug}] Scraping images...")
    images = scrape_images(match, count=6)

    logger.info(f"[{slug}] Generating formal style...")
    formal_audio = generate_voiceover(scripts.formal_script, f"{slug}_formal", "formal")
    formal_video = assemble_video(images, formal_audio, f"{slug}_formal", speed=1.4) if formal_audio and images else None

    logger.info(f"[{slug}] Generating casual style...")
    casual_audio = generate_voiceover(scripts.casual_script, f"{slug}_casual", "casual")
    casual_video = assemble_video(images, casual_audio, f"{slug}_casual", speed=1.4) if casual_audio and images else None

    tiktok_ok = _tiktok_available()

    return {
        "match_id": match.id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "score": f"{match.home_score} - {match.away_score}",
        "formal_video": str(formal_video) if formal_video else None,
        "casual_video": str(casual_video) if casual_video else None,
        "formal_script": scripts.formal_script[:100],
        "casual_script": scripts.casual_script[:100],
        "tiktok_formal": _upload_to_tiktok(formal_video, match, "formal") if tiktok_ok else None,
        "tiktok_casual": _upload_to_tiktok(casual_video, match, "casual") if tiktok_ok else None,
    }


def _upload_to_tiktok(video_path, match, style: str) -> dict | None:
    """Upload via Playwright browser automation."""
    if not video_path:
        return None
    try:
        from src.tiktok_browser import upload_video
        caption = _build_tiktok_caption(match, style)
        ok, msg = upload_video(str(video_path), caption)
        if ok:
            logger.info(f"TikTok upload OK ({style}): {msg}")
        else:
            logger.error(f"TikTok upload failed ({style}): {msg}")
        return {"success": ok, "error": msg if not ok else None}
    except Exception as e:
        logger.error(f"TikTok upload exception ({style}): {e}")
        return {"success": False, "error": str(e)}


def _build_tiktok_caption(match, style: str) -> str:
    score = f"{match.home_team} {match.home_score} - {match.away_score} {match.away_team}"
    if style == "formal":
        return f"{score} | የዓለም ዋንጫ 2026 ውጤቶች #WorldCup2026 #FIFA #Soccer #Football"
    else:
        return f"😱 {score}! ምን ጨዋታ ነበር! #WorldCup2026 #FIFA #Soccer #Football #FYP"


if __name__ == "__main__":
    results = run_pipeline()
    print(f"Done: {len(results)} matches")
    for r in results:
        print(f"  {r['home_team']} vs {r['away_team']} → {r['formal_video']} | {r['casual_video']}")
