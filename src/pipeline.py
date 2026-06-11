"""Orchestrator: runs the full pipeline for each finished match."""
from src.match_data import fetch_todays_matches
from src.script_gen import generate_scripts
from src.image_scraper import scrape_images
from src.voiceover import generate_voiceover
from src.video_assembler import assemble_video
from src.utils import get_logger

logger = get_logger(__name__)


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
    formal_video = assemble_video(images, formal_audio, f"{slug}_formal") if formal_audio and images else None

    logger.info(f"[{slug}] Generating casual style...")
    casual_audio = generate_voiceover(scripts.casual_script, f"{slug}_casual", "casual")
    casual_video = assemble_video(images, casual_audio, f"{slug}_casual") if casual_audio and images else None

    return {
        "match_id": match.id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "score": f"{match.home_score} - {match.away_score}",
        "formal_video": str(formal_video) if formal_video else None,
        "casual_video": str(casual_video) if casual_video else None,
        "formal_script": scripts.formal_script[:100],
        "casual_script": scripts.casual_script[:100],
    }


if __name__ == "__main__":
    results = run_pipeline()
    print(f"Done: {len(results)} matches")
    for r in results:
        print(f"  {r['home_team']} vs {r['away_team']} → {r['formal_video']} | {r['casual_video']}")
