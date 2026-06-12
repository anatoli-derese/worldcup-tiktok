"""
Self-contained pipeline runner for cron jobs.
Usage: python scripts/run_match.py canada_bosnia
Reads match schedule from data/upcoming_matches.json,
scrapes live scores, generates video, uploads to TikTok.
"""
import sys, json, os, subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def get_match_score(match):
    """Try to get the live score from public sources."""
    home, away = match["home"], match["away"]
    
    # Try football-data.org free tier (no key = limited)
    # Fall back to web scraping
    import urllib.request, re
    
    try:
        # Try ESPN API or Wikipedia for the match result
        url = f"https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode()
        
        # Look for the match in Wikipedia tables
        # Pattern: Home Team X-X Away Team
        for pattern in [
            rf"{re.escape(home)}.*?(\d+)[–\-](\d+).*?{re.escape(away)}",
            rf"{re.escape(away)}.*?(\d+)[–\-](\d+).*?{re.escape(home)}",
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                if home.lower() in html[m.start():m.end()].lower():
                    return int(m.group(1)), int(m.group(2))
                else:
                    return int(m.group(2)), int(m.group(1))
    except Exception as e:
        print(f"  Score scrape failed: {e}")
    
    return None, None


def run_match(slug):
    """Run full pipeline for a match."""
    schedule = json.loads((ROOT / "data/upcoming_matches.json").read_text())
    match = next((m for m in schedule if m["slug"] == slug), None)
    if not match:
        print(f"Match '{slug}' not found")
        return
    
    print(f"\n{'='*50}")
    print(f"Processing: {match['home']} vs {match['away']}")
    print(f"{'='*50}")
    
    # Try to get score
    home_score, away_score = get_match_score(match)
    
    if home_score is None:
        print("Match not finished yet or scores unavailable. Skipping.")
        return
    
    print(f"Score: {match['home']} {home_score} - {away_score} {match['away']}")
    
    # Build match object
    class M:
        id = slug
        home_team = match["home"]
        away_team = match["away"]
        home_score_val = home_score
        away_score_val = away_score
        events = []
    
    m = M()
    
    # Generate scripts (Gemini if available, fallback otherwise)
    try:
        from src.script_gen import generate_scripts
        scripts = generate_scripts(m)
        print(f"Scripts: Gemini OK ({len(scripts.formal_script)} chars)")
    except Exception as e:
        print(f"Gemini unavailable ({e}), using template")
        formal = f"{m.home_team} {m.home_score_val}-{m.away_score_val} {m.away_team}ን አሸንፏል! የዓለም ዋንጫ 2026 አስደናቂ ጨዋታ።"
        casual = f"{m.home_team} {m.away_team}ን {m.home_score_val}-{m.away_score_val} አሸንፋለች! ምን ጨዋታ ነበር! 😱"
        class Scripts:
            formal_script = formal
            casual_script = casual
        scripts = Scripts()
    
    # Images
    from src.image_scraper import scrape_images
    print("Scraping images...")
    images = scrape_images(m, count=5)
    print(f"  Got {len(images)} images")
    
    # Voiceover + Video
    from src.voiceover import generate_voiceover
    from src.video_assembler import assemble_video
    
    for style, script in [("formal", scripts.formal_script), ("casual", scripts.casual_script)]:
        print(f"\n--- {style.upper()} ---")
        
        audio = generate_voiceover(script, f"{slug}_{style}", style)
        if not audio:
            print("  Voiceover failed, skipping")
            continue
        
        video = assemble_video(images, audio, f"{slug}_{style}", speed=1.4)
        if not video:
            print("  Video assembly failed")
            continue
        
        print(f"  Video: {video}")
        
        # Upload to TikTok
        try:
            from src.tiktok_browser import upload_video
            score_str = f"{m.home_team} {m.home_score_val}-{m.away_score_val} {m.away_team}"
            if style == "formal":
                caption = f"{score_str} | የዓለም ዋንጫ 2026 #WorldCup2026 #FIFA"
            else:
                caption = f"😱 {score_str}! #WorldCup2026 #FIFA #FYP"
            
            ok, msg = upload_video(str(video), caption)
            print(f"  TikTok: {'OK' if ok else 'FAIL'} - {msg}")
        except Exception as e:
            print(f"  TikTok upload error: {e}")
    
    print(f"\n{'='*50}")
    print(f"Done: {match['home']} vs {match['away']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_match.py <slug>")
        sys.exit(1)
    
    os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")
    os.chdir(str(ROOT))
    run_match(sys.argv[1])
