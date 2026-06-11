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
    match_slug = (
        f"{match.home_team.lower()}_{match.away_team.lower()}"
        .replace(" ", "_")
        .replace(".", "")
    )

    # Step 1: Generate scripts
    logger.info(f"[{match_slug}] Generating scripts...")
    scripts = generate_scripts(match)

    # Step 2: Scrape images
    logger.info(f"[{match_slug}] Scraping images...")
    images = scrape_images(match, count=6)

    # Step 3: Generate formal voiceover + video
    logger.info(f"[{match_slug}] Generating formal voiceover...")
    formal_audio = generate_voiceover(
        scripts.formal_script,
        output_name=f"{match_slug}_formal",
        voice_style="formal",
    )
    formal_video = None
    if formal_audio and images:
        formal_video = assemble_video(
            images, formal_audio, output_name=f"{match_slug}_formal"
        )

    # Step 4: Generate casual voiceover + video
    logger.info(f"[{match_slug}] Generating casual voiceover...")
    casual_audio = generate_voiceover(
        scripts.casual_script,
        output_name=f"{match_slug}_casual",
        voice_style="casual",
    )
    casual_video = None
    if casual_audio and images:
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
