#!/usr/bin/env python3
"""
Football/Soccer Match Image Scraper — Production-Ready
======================================================
Multi-source scraper for real football match photos. No API keys needed.
Sources ranked by reliability for real match photos:
  1. Startpage (proxies Google Images) — real editorial/news photos
  2. Flickr Public Feed — CC-licensed fan/match photos  
  3. BBC Sport RSS — editorial sports photography
Fallback: Generated match cards with team colors + score overlay.

Usage:
    from football_image_scraper import scrape_match_images
    images = scrape_match_images("Brazil", "Germany", count=6)
    # Returns list of (PIL.Image, source_label) tuples
"""

import io, re, time, json
import requests
from urllib.parse import quote_plus, unquote
from PIL import Image
from pathlib import Path
from typing import Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# SOURCE 1: Startpage (proxies Google Images) — BEST
# ============================================================

def scrape_startpage(query: str, max_results: int = 15) -> list[tuple[str, str]]:
    """
    Scrape Startpage image search. Returns list of (image_url, source_domain).
    Startpage proxies Google Images through a privacy layer, so we get
    real editorial/news photos from major outlets.
    Rate limit: Be respectful, 3-5 queries/minute.
    """
    try:
        url = f"https://www.startpage.com/sp/search?query={quote_plus(query)}&cat=images"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        # Extract proxied image URLs. Format: piurl=https%3A%2F%2F...
        piurls = re.findall(r'piurl=(https?%3A%2F%2F[^&"]+)', r.text)
        decoded = [unquote(u) for u in piurls]
        
        # Filter to actual image file extensions
        img_extensions = ('.jpg', '.jpeg', '.png', '.webp')
        image_urls = [u for u in decoded if any(u.lower().endswith(ext) for ext in img_extensions)]
        
        # Filter out icons/logos/thumbnails
        bad_patterns = ['favicon', 'logo', 'icon', 'avatar', 'thumb-', 'thumbnail',
                       'gravatar', 'pixel', 'spacer', 'placeholder']
        image_urls = [u for u in image_urls 
                     if not any(p in u.lower() for p in bad_patterns)]
        
        # Deduplicate
        seen = set()
        unique = []
        for u in image_urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        
        results = [(u, u.split('/')[2]) for u in unique[:max_results]]
        return results
    except Exception:
        return []


# ============================================================
# SOURCE 2: Flickr Public Feed — no API key needed
# ============================================================

def scrape_flickr(tags: str, max_results: int = 10) -> list[tuple[str, str]]:
    """
    Search Flickr's public feed by tags. Returns list of (image_url, title).
    Images are CC-licensed. Use tagmode=all for stricter matching.
    """
    try:
        url = (
            f"https://api.flickr.com/services/feeds/photos_public.gne"
            f"?tags={quote_plus(tags)}&tagmode=all"
            f"&format=json&nojsoncallback=1"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        data = r.json()
        items = data.get("items", [])
        
        results = []
        for item in items[:max_results]:
            media_url = item.get("media", {}).get("m", "")
            # Convert thumbnail to larger version (_m -> _b or _c)
            large_url = media_url.replace("_m.jpg", "_b.jpg")
            title = item.get("title", "Unknown")
            results.append((large_url, f"Flickr: {title[:60]}"))
        
        return results
    except Exception:
        return []


# ============================================================
# SOURCE 3: BBC Sport RSS — editorial football photos
# ============================================================

def scrape_bbc_sport(max_results: int = 10) -> list[tuple[str, str]]:
    """
    Extract images from BBC Sport football RSS feed.
    Returns high-res (1024px) editorial sports photos.
    """
    try:
        r = requests.get("https://feeds.bbci.co.uk/sport/football/rss.xml", 
                         headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        # Extract thumbnail URLs and upgrade to high-res
        thumbnails = re.findall(r'<media:thumbnail[^>]*url="([^"]+)"', r.text)
        
        results = []
        for thumb in thumbnails[:max_results]:
            # BBC URL pattern: .../240/cpsprodpb/... → /1024/...
            large = re.sub(r'/240/', '/1024/', thumb)
            large = re.sub(r'/ace/standard/', '/ace/ws/', large)
            results.append((large, f"BBC Sport"))
        
        return results
    except Exception:
        return []


# ============================================================
# SOURCE 4: Sky Sports RSS
# ============================================================

def scrape_skysports(max_results: int = 10) -> list[tuple[str, str]]:
    """Extract images from Sky Sports RSS feed."""
    try:
        r = requests.get("https://www.skysports.com/rss/12040",
                         headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        
        imgs = re.findall(r'<media:content[^>]*url="([^"]+)"', r.text)
        results = [(u, "Sky Sports") for u in imgs[:max_results]]
        return results
    except Exception:
        return []


# ============================================================
# DOWNLOAD & VALIDATE
# ============================================================

def download_image(url: str, min_bytes: int = 15000, timeout: int = 12) -> Optional[Image.Image]:
    """Download and validate an image. Returns PIL Image or None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200 and len(r.content) > min_bytes:
            return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        pass
    return None


# ============================================================
# MATCH CARD GENERATOR (fallback)
# ============================================================

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
    "croatia": ("#ff0000", "#ffffff"),
    "uruguay": ("#87cefa", "#000000"),
    "default": ("#1a1a2e", "#e94560"),
}

def generate_match_card(text: str, bg_color: str, accent_color: str, 
                        width: int = 1080, height: int = 1920) -> Image.Image:
    """Generate a professional TikTok-style match card."""
    from PIL import ImageDraw, ImageFont
    
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Accent bars
    draw.rectangle([(0, 0), (width, 8)], fill=accent_color)
    draw.rectangle([(0, height - 8), (width, height)], fill=accent_color)
    
    # Try to load fonts, fall back to default
    try:
        font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    except OSError:
        font_main = ImageFont.load_default()
    
    # Center text
    lines = text.split("\n")
    y = 500
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_main)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, fill="#ffffff", font=font_main)
        y += 120
    
    return img


# ============================================================
# MAIN SCRAPE FUNCTION
# ============================================================

def scrape_match_images(home_team: str, away_team: str, 
                        count: int = 6,
                        sources: list[str] = None) -> list[tuple[Image.Image, str]]:
    """
    Scrape real football match images for a given fixture.
    
    Args:
        home_team: Home team name (e.g., "Brazil")
        away_team: Away team name (e.g., "Germany") 
        count: Number of images needed
        sources: Ordered list of sources to try. Default:
                 ['startpage', 'flickr', 'bbc', 'skysports']
    
    Returns:
        List of (PIL.Image, source_label) tuples
    """
    if sources is None:
        sources = ['startpage', 'flickr', 'bbc']
    
    images = []
    
    for source in sources:
        if len(images) >= count:
            break
            
        urls_with_labels = []
        
        if source == 'startpage':
            query = f"{home_team} {away_team} world cup football match action"
            urls_with_labels = scrape_startpage(query, max_results=10)
            time.sleep(1)  # Be polite
            
            # Also try a celebration query if we need more
            if len(urls_with_labels) < 3:
                query2 = f"world cup {home_team} {away_team} goal celebration"
                urls_with_labels += scrape_startpage(query2, max_results=8)
                time.sleep(1)
        
        elif source == 'flickr':
            tags = f"worldcup,{home_team.lower()},{away_team.lower()}"
            urls_with_labels = scrape_flickr(tags, max_results=8)
            time.sleep(0.5)
            
            if len(urls_with_labels) < 3:
                tags2 = "worldcup,football,match,action"
                urls_with_labels += scrape_flickr(tags2, max_results=6)
                time.sleep(0.5)
        
        elif source == 'bbc':
            urls_with_labels = scrape_bbc_sport(max_results=8)
        
        elif source == 'skysports':
            urls_with_labels = scrape_skysports(max_results=8)
        
        # Download and validate
        for url, label in urls_with_labels:
            if len(images) >= count:
                break
            img = download_image(url)
            if img:
                images.append((img, label))
                time.sleep(0.3)  # Rate limit downloads
    
    # Fallback: generate match cards
    while len(images) < count:
        home_color, home_accent = TEAM_COLORS.get(
            home_team.lower(), TEAM_COLORS["default"])
        
        if len(images) == 0:
            card_text = f"{home_team}\nVS\n{away_team}"
        elif len(images) == 1:
            card_text = "MATCH\nHIGHLIGHTS"
        else:
            card_text = f"GOAL!\n{home_team}"
        
        card = generate_match_card(card_text, home_color, home_accent)
        images.append((card, "generated_card"))
    
    return images[:count]


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Football Image Scraper - Live Test")
    print("=" * 60)
    
    for home, away in [("Brazil", "Germany"), ("Argentina", "France")]:
        print(f"\n{'='*40}")
        print(f"Scraping: {home} vs {away}")
        print(f"{'='*40}")
        
        images = scrape_match_images(home, away, count=5)
        
        for i, (img, source) in enumerate(images):
            print(f"  [{i}] {img.size[0]}x{img.size[1]} — Source: {source}")
        
        time.sleep(3)  # Rate limit between matches
    
    print("\n✓ Done!")
