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
    print("Skipped - missing audio or images")

print("\n=== DONE ===")
