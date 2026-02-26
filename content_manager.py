import json
import os
import logging
import requests
import random
import re
import time
import asyncio
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

STATE_FILE = "bot_state.json"
BASE_URL = "https://cinma.online"
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Attempt to import playwright for headless scraping
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Scraper will use requests (might fail Cloudflare).")

def get_next_content_type():
    """Implements 3 Movies : 1 Series rotation."""
    if not os.path.exists(STATE_FILE):
        state = {"movie_count": 0}
    else:
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
        except:
            state = {"movie_count": 0}

    if state["movie_count"] < 3:
        content_type = "Movie"
        state["movie_count"] += 1
    else:
        content_type = "Series"
        state["movie_count"] = 0
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    
    return content_type

def get_tmdb_data(title, content_type):
    """Fetches popularity and metadata from TMDB."""
    if not TMDB_API_KEY:
        return 0, [], "", "", "N/A"
    
    search_type = "movie" if content_type.lower() == "movie" else "tv"
    url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={title}"
    
    try:
        res = requests.get(url, timeout=10).json()
        if res.get('results'):
            best_match = res['results'][0]
            return (
                best_match.get('popularity', 0),
                best_match.get('genre_ids', []),
                best_match.get('overview', ''),
                best_match.get('poster_path', ''),
                best_match.get('id', 'N/A')
            )
    except Exception as e:
        logger.error(f"TMDB lookup failed for {title}: {e}")
    
    return 0, [], "", "", "N/A"

from supabase import create_client, Client

from dotenv import load_dotenv
load_dotenv()

# Site configuration from Environment Variables
SITE_SUPABASE_URL = os.getenv("SUPABASE_URL")
SITE_SUPABASE_KEY = os.getenv("SUPABASE_KEY")

import sys

def scrape_cinma_online():
    """Fetches latest content directly from cinma.online's Supabase backend."""
    logger.info("Fetching latest content from Supabase backend...")
    
    # --- Load posted_ids to filter ---
    posted_ids = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                posted_ids = [str(pid) for pid in state.get("posted_ids", [])]
        except: pass

    catalog = []
    try:
        client: Client = create_client(SITE_SUPABASE_URL, SITE_SUPABASE_KEY)
        
        # Fetch latest movies
        movies_res = client.table('movies').select('id, title, arabic_title, trailer_url').order('created_at', desc=True).limit(50).execute()
        for movie in movies_res.data:
            m_id = str(movie['id'])
            if m_id in posted_ids:
                continue
            title = movie.get('title') or movie.get('arabic_title') or f"Movie {movie['id']}"
            catalog.append({
                'id': m_id,
                'title': title,
                'type': 'Movie',
                'watch_url': f"{BASE_URL}/watch/movie/{movie['id']}",
                'poster_url': None,
                'trailer_url': movie.get('trailer_url')
            })
            
        # Fetch latest series
        series_res = client.table('series').select('id, title').order('created_at', desc=True).limit(30).execute()
        for series in series_res.data:
            s_id = str(series['id'])
            if s_id in posted_ids:
                continue
            title = series.get('title') or f"Series {series['id']}"
            catalog.append({
                'id': s_id,
                'title': title,
                'type': 'Series',
                'watch_url': f"{BASE_URL}/watch/series/{series['id']}",
                'poster_url': None,
                'trailer_url': None
            })
            
        if not catalog and posted_ids:
            logger.warning("All fetched content from Supabase has already been posted. Waiting for new content...")
            return []

        logger.info(f"Retrieved {len(catalog)} new items from Supabase (filtered).")
        return catalog
    except Exception as e:
        logger.error(f"Supabase extraction failed: {e}")
        # Fallback to empty list or your previous BeautifulSoup logic if you want
        return []

async def extract_assets_from_page(watch_url):
    """Scrapes a specific watch page to find the trailer URL."""
    logger.info(f"Scraping watch page: {watch_url}")
    html_content = ""

    if PLAYWRIGHT_AVAILABLE:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(watch_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
                html_content = await page.content()
                await browser.close()
        except Exception as e:
            logger.error(f"Playwright asset extraction failed: {e}")

    if not html_content:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(watch_url, headers=headers, timeout=15)
            html_content = response.text
        except: pass

    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        youtube_regex = re.compile(r'(youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)')
        
        # 1. Check iframes
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            match = youtube_regex.search(src)
            if match:
                return f"https://www.youtube.com/watch?v={match.group(2)}"
        
        # 2. Check all links
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            match = youtube_regex.search(href)
            if match:
                return f"https://www.youtube.com/watch?v={match.group(2)}"
            
        return None
    except Exception as e:
        logger.error(f"Asset extraction failed: {e}")
        return None

async def extract_overview_text(watch_url):
    logger.info(f"Scraping overview: {watch_url}")
    html_content = ""
    if PLAYWRIGHT_AVAILABLE:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(watch_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
                html_content = await page.content()
                await browser.close()
        except Exception as e:
            logger.error(f"Playwright overview extraction failed: {e}")
    if not html_content:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(watch_url, headers=headers, timeout=15)
            html_content = response.text
        except:
            pass
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        candidates = []
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            candidates.append(meta_desc['content'])
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            candidates.append(og_desc['content'])
        prop_desc = soup.select('[itemprop="description"]')
        for el in prop_desc:
            candidates.append(el.get_text(separator=' ', strip=True))
        def class_match(c):
            try:
                cl = ' '.join(c) if isinstance(c, list) else str(c)
                cl = cl.lower()
                return any(k in cl for k in ['overview', 'synopsis', 'story', 'description'])
            except:
                return False
        desc_blocks = [el for el in soup.find_all(True) if class_match(el.get('class'))]
        for el in desc_blocks:
            candidates.append(el.get_text(separator=' ', strip=True))
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(separator=' ', strip=True)
            if len(text) > 200:
                candidates.append(text)
        candidates = [re.sub(r'\s+', ' ', t).strip() for t in candidates if t and isinstance(t, str)]
        if not candidates:
            return ""
        longest = max(candidates, key=len)
        return longest
    except Exception as e:
        logger.error(f"Overview extraction failed: {e}")
        return ""
async def select_best_content():
    """Dynamically scrapes, enriches, and selects content."""
    catalog = scrape_cinma_online()
    
    # --- FALLBACK TO LOCAL CATALOG IF SCRAPER FAILS ---
    if not catalog:
        logger.warning("Scraper failed to find items. Falling back to local catalog.csv for stability.")
        if os.path.exists("catalog.csv"):
            import csv
            catalog = []
            try:
                with open("catalog.csv", mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        catalog.append({
                            'title': row.get('Title'),
                            'type': row.get('Type'),
                            'watch_url': row.get('Watch_URL'),
                            'poster_url': None
                        })
            except Exception as e:
                logger.error(f"Error reading catalog.csv: {e}")
                return None
        else:
            logger.error("No catalog.csv found and scraper failed. Exiting.")
            return None
    # --------------------------------------------------

    target_type = get_next_content_type()
    logger.info(f"Target content type: {target_type}")

    filtered_items = [item for item in catalog if item['type'] == target_type]
    if not filtered_items:
        logger.warning(f"No {target_type} found. Falling back.")
        filtered_items = catalog

    # Enrich with TMDB
    results = []
    # Limit to top 15 items for better variety and scoring
    for item in filtered_items[:15]:
        title = item['title']
        pop, genres, overview, tmdb_poster, tmdb_id = get_tmdb_data(title, item['type'])
        
        # High Retention Genre Scoring (Retention Rate Optimization)
        # 878: Sci-Fi, 35: Comedy, 18: Drama, 9648: Mystery, 53: Thriller
        score = pop
        
        # Boost based on Genres
        if 878 in genres: # Sci-Fi / Time Travel
            score *= 2.0
        if 35 in genres: # Comedy
            score *= 1.8
        if 9648 in genres or 53 in genres: # Mystery/Thriller (Suspense)
            score *= 1.7
        if 18 in genres: # Drama (Success/Karma stories)
            score *= 1.5
            
        # Boost based on Keywords in Overview (Success, Karma, Zero to Hero, Time Travel)
        ov_lower = overview.lower()
        high_retention_keywords = ["time travel", "success", "karma", "zero to hero", "from zero", "destiny", "revenge"]
        for kw in high_retention_keywords:
            if kw in ov_lower:
                score *= 1.3
                break # Only one boost for keywords
            
        results.append({
            'Title': title,
            'Type': item['type'],
            'Watch_URL': item['watch_url'],
            'Poster_URL': item['poster_url'] or (f"https://image.tmdb.org/t/p/w500{tmdb_poster}" if tmdb_poster else None),
            'popularity_score': score,
            'overview': overview,
            'tmdb_id': tmdb_id,
            'genre_ids': genres
        })

    results.sort(key=lambda x: x['popularity_score'], reverse=True)
    if not results:
        return None
        
    # Pick a random item from the top 3 to ensure we pick high-quality but avoid total repetition
    top_n = min(len(results), 3)
    selected = random.choice(results[:top_n])
    
    # Finally, try to get the trailer directly from the site
    trailer_url = await extract_assets_from_page(selected['Watch_URL'])
    selected['Trailer_URL'] = trailer_url
    
    page_overview = await extract_overview_text(selected['Watch_URL'])
    if page_overview and len(page_overview) > len(selected.get('overview', '')):
        selected['overview'] = page_overview
    else:
        if len((selected.get('overview') or '')) < 400:
            selected['overview'] = f"{selected.get('overview') or ''}\n\nIf the overview is short, use your internal knowledge to expand the movie's story to reach 150 words."
    
    logger.info(f"Selected: {selected['Title']} (Trailer: {trailer_url})")
    return selected
