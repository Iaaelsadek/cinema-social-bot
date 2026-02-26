import os
import sys
import time
import json
import random

# Ensure directories exist immediately
OUTPUT_DIR = "output"
TEMP_DIR = "temp"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# --- Dynamic Random Scheduling ---
STATE_FILE = "bot_state.json"

def check_scheduling():
    """Checks if it's time to post based on randomized interval."""
    if os.environ.get("FORCE_POST") == "true":
        logger.info("🚀 FORCE_POST detected! Bypassing schedule...")
        return

    if not os.path.exists(STATE_FILE):
        logger.info("No bot_state.json found. Proceeding with first run...")
        # Initialize with default values if it doesn't exist
        state = {
            "last_post_timestamp": 0,
            "next_interval_seconds": 0,
            "posted_ids": [],
            "movie_count": 0
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
        return
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        
        # Ensure posted_ids exists
        if "posted_ids" not in state:
            state["posted_ids"] = []
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=4)
        
        last_post = state.get("last_post_timestamp", 0)
        next_interval = state.get("next_interval_seconds", 0)
        
        current_time = time.time()
        elapsed = current_time - last_post
        
        if elapsed < next_interval:
            remaining_mins = int((next_interval - elapsed) / 60)
            logger.info(f"⏳ الانتظار للجدول العشوائي... النشر القادم بعد {remaining_mins} دقيقة.")
            sys.exit(0)
        else:
            logger.info(f"Schedule reached! Elapsed: {int(elapsed/3600)}h. Interval was: {int(next_interval/3600)}h.")
    except Exception as e:
        logger.warning(f"Error checking schedule: {e}. Proceeding anyway...")

def update_scheduling(content_id=None):
    """Updates bot_state.json with new random interval and marks content as posted."""
    try:
        new_interval = random.randint(5 * 3600, 7 * 3600) # 5-7 hours
        
        # Read current state to preserve posted_ids and movie_count
        state = {"posted_ids": [], "movie_count": 0}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
            except: pass

        state.update({
            "last_post_timestamp": time.time(),
            "next_interval_seconds": new_interval,
            "last_post_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        if content_id:
            if "posted_ids" not in state:
                state["posted_ids"] = []
            if str(content_id) not in state["posted_ids"]:
                state["posted_ids"].append(str(content_id))
                logger.info(f"Marked ID {content_id} as posted.")

        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
        logger.info(f"✅ Schedule updated: Next post in {int(new_interval/3600)} hours.")
    except Exception as e:
        logger.error(f"Failed to update schedule: {e}")

import platform
# MONKEY PATCH: Fix broken WMI on user system (CRITICAL)
if platform.system() == 'Windows':
    platform.machine = lambda: "AMD64"
    platform.processor = lambda: "AMD64"
    platform.system = lambda: "Windows"
    platform.release = lambda: "10"
    platform.version = lambda: "10.0.19041"
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19041', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda: "Windows-10-10.0.19041-SP0"
    platform.node = lambda: "DESKTOP-USER"

import requests
import asyncio
import re
import glob
import traceback
import logging
import shutil
import subprocess
import gc
import cv2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Set environment variables for memory management
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# RICH UI IMPORTS
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn
from rich.live import Live

# SETUP RICH CONSOLE & LOGGING
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("rich")

# Global Progress Manager for yt-dlp
def get_progress_manager():
    return Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        transient=True
    )

def download_with_rich(ydl_opts, urls):
    """Helper to run yt-dlp with Rich progress bar."""
    with get_progress_manager() as progress:
        task_id = progress.add_task("Starting...", filename="Init", total=100)
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    filename = os.path.basename(d.get('filename', 'Unknown'))
                    p = d.get('_percent_str', '0%').replace('%','')
                    progress.update(task_id, completed=float(p), filename=filename)
                except:
                    pass
            elif d['status'] == 'finished':
                progress.update(task_id, completed=100, description="[green]Finished!")

        # Add hook to options
        ydl_opts['progress_hooks'] = [progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(urls)


from content_manager import select_best_content
from dotenv import load_dotenv
import edge_tts
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
import yt_dlp
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from supabase import create_client, Client
from google import genai

# MoviePy Imports
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, 
    concatenate_videoclips, ImageClip, concatenate_audioclips, 
    AudioArrayClip, ColorClip
)
import moviepy.video.fx as vfx
from moviepy.audio.AudioClip import CompositeAudioClip
import moviepy.audio.fx as afx
import imageio_ffmpeg

# Whisper (Lazy Import)
whisper = None

def get_whisper():
    global whisper
    if whisper is None:
        import whisper as _whisper
        whisper = _whisper
    return whisper

# -----------------------------------------------------------------------------
# LOCKED CONFIGURATION
# -----------------------------------------------------------------------------
# SECURITY WARNING: This file is LOCKED. 
# Do NOT modify Intro/Outro logic, Prompt structure, or Core Logic without 
# explicit User Authorization (Password: 26634095).
# -----------------------------------------------------------------------------

# Load environment variables
load_dotenv()

# Configure Logging - REMOVED (Handled by Rich)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# --- Constants & Settings ---
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ALIBABA_API_KEY = os.environ.get("ALIBABA_API_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

OUTPUT_DIR = "output"
TEMP_DIR = "temp"
VIRAL_QUEUE_FILE = "viral_queue.json"
VIRAL_LINKS_FILE = "viral_links.txt"

# Branding
WEBSITE_TEXT = "www.cinma.online"
FONT_SIZE = 19
TEXT_MARGIN_BOTTOM = 15
TEXT_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 2

# Modes
TEST_MODE = False               # Set to False for production
DEBUG_SHORT_VIDEO = False       # Force 5-second video for testing
ENABLE_VIDEO_GENERATION = True  # ENABLED
SIMULATION_MODE = False         # PRODUCTION MODE: ENABLE UPLOAD

# Email Configuration
ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

# Genre Mapping (TMDB ID -> Arabic)
GENRE_MAP = {
    28: "الأكشن", 12: "المغامرة", 16: "الأنيميشن", 35: "الكوميدي",
    80: "الجريمة", 99: "الوثائقي", 18: "الدراما", 10751: "العائلي",
    14: "الخيال", 36: "التاريخي", 27: "الرعب", 10402: "الموسيقي",
    9648: "الغموض", 10749: "الرومانسي", 878: "الخيال العلمي",
    10770: "التلفزيوني", 53: "الإثارة", 10752: "الحربي", 37: "الويسترن"
}

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def send_telegram_alert(message):
    """Sends a notification message to Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram credentials missing. Skipping alert.")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        logger.info("Telegram alert sent.")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")

def send_error_email(subject, message):
    """Sends an email alert when a critical error occurs."""
    logger.info(f"Sending error email: {subject}")
    if not ALERT_EMAIL or not ALERT_EMAIL_PASSWORD:
        logger.error("Email credentials not set in .env (ALERT_EMAIL, ALERT_EMAIL_PASSWORD). Skipping email.")
        return

    msg = MIMEMultipart()
    msg['From'] = ALERT_EMAIL
    msg['To'] = "cairo.tv@gmail.com"
    msg['Subject'] = f"CinemaBot Error: {subject}"
    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(ALERT_EMAIL, ALERT_EMAIL_PASSWORD)
        server.sendmail(ALERT_EMAIL, "cairo.tv@gmail.com", msg.as_string())
        server.quit()
        logger.info("Error email sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def send_alert_email(failed_url, error_msg):
    """Sends an alert email when a viral video fails."""
    sender = os.environ.get("ALERT_EMAIL_SENDER")
    password = os.environ.get("ALERT_EMAIL_PASSWORD")
    receiver = os.environ.get("ALERT_EMAIL_RECEIVER")
    
    if not sender or not password or not receiver:
        logger.warning("Email credentials not set (ALERT_EMAIL_SENDER/PASSWORD/RECEIVER). Skipping alert.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = "Cinema Bot Alert: Viral Video Skipped"
    
    body = f"Failed URL: {failed_url}\nError: {error_msg}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        logger.info(f"Alert email sent for {failed_url}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")

def get_watch_url_from_supabase(movie_title: str) -> str:
    """
    Fetches the watch URL from Supabase.
    STRICT MODE: No default link. Sends email and exits on failure.
    """
    try:
        from content_manager import SITE_SUPABASE_URL, SITE_SUPABASE_KEY, BASE_URL
    except Exception:
        SITE_SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SITE_SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        BASE_URL = "https://cinma.online"
    
    error_msg = ""
    try:
        if not SITE_SUPABASE_URL or not SITE_SUPABASE_KEY:
            error_msg = "Supabase credentials missing."
            raise ValueError(error_msg)
        
        client: Client = create_client(SITE_SUPABASE_URL, SITE_SUPABASE_KEY)
        
        # Helper to process result
        def process_result(data):
            if data:
                m = data[0]
                slug = m.get('slug')
                if slug and isinstance(slug, str) and slug.startswith("http"):
                    return slug
                return f"{BASE_URL}/watch/movie/{m['id']}"
            return None

        # 1. Try exact match on title OR arabic_title OR original_title
        try:
            query = f'title.eq."{movie_title}",arabic_title.eq."{movie_title}",original_title.eq."{movie_title}"'
            res = client.table('movies').select('id, title, arabic_title, slug').or_(query).limit(1).execute()
            url = process_result(res.data)
            if url: return url
        except Exception as e:
            logger.warning(f"Supabase exact match error: {e}")

        # 2. Try ilike on title
        try:
            res = client.table('movies').select('id, title, arabic_title, slug').ilike('title', f"%{movie_title}%").limit(1).execute()
            url = process_result(res.data)
            if url: return url
        except Exception: pass

        # 3. Try ilike on arabic_title
        try:
            res = client.table('movies').select('id, title, arabic_title, slug').ilike('arabic_title', f"%{movie_title}%").limit(1).execute()
            url = process_result(res.data)
            if url: return url
        except Exception: pass
        
        # If we reach here, no URL was found
        error_msg = f"Movie '{movie_title}' not found in Supabase."
            
    except Exception as e:
        error_msg = f"Supabase connection error: {e}"
        logger.error(error_msg)
    
    # STRICT FAILURE HANDLING
    logger.critical(f"CRITICAL: {error_msg}")
    send_error_email("Supabase Watch URL Failed", f"Could not fetch watch URL for '{movie_title}'.\nReason: {error_msg}\n\nThe bot has been stopped.")
    sys.exit(1)

import contextlib

def clean_temp_files():
    """Cleans all temporary and output files to prevent caching issues."""
    logger.info("Cleaning temporary files...")
    
    # 1. Clean directories
    for directory in [TEMP_DIR, OUTPUT_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                with contextlib.suppress(FileNotFoundError, PermissionError):
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        # Retry logic for locked files
                        for _ in range(3):
                            try:
                                os.unlink(file_path)
                                break
                            except PermissionError:
                                time.sleep(1)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
        else:
            os.makedirs(directory)

    # 2. Clean root directory temp files (MoviePy leftovers)
    root_patterns = ["*TEMP_MPY_wvf_snd.mp3", "*.mp3", "*.mp4"]
    for pattern in root_patterns:
        try:
            root_files = glob.glob(pattern)
            for f in root_files:
                with contextlib.suppress(FileNotFoundError, PermissionError):
                    os.remove(f)
                    logger.info(f"Removed root temp file: {f}")
        except Exception as e:
            logger.warning(f"Root cleanup failed for pattern {pattern}: {e}")

    logger.info("Temp and Output directories cleaned.")

# --- FFmpeg Configuration ---
# Headless Cloud Support: Use system ffmpeg if ffmpeg.exe is not present
if os.path.exists("ffmpeg.exe"):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.abspath("ffmpeg.exe")
    ffmpeg_path = os.path.abspath("ffmpeg.exe")
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
    logger.info("Using local ffmpeg.exe")
else:
    logger.info("ffmpeg.exe not found, using system FFmpeg")

if shutil.which("ffmpeg") is None:
    logger.warning("FFmpeg not found in PATH")
else:
    logger.info("FFmpeg configured successfully.")

# -----------------------------------------------------------------------------
# Core Functions
# -----------------------------------------------------------------------------

def get_movie():
    """Fetches the latest movie from Supabase with poster URL."""
    if not supabase:
        logger.error("Supabase client not initialized.")
        return None, None, None
    try:
        response = supabase.table('movies').select('*').order('created_at', desc=True).limit(1).execute()
        if response.data:
            movie = response.data[0]
            # Assuming poster_path is stored in Supabase (from TMDB)
            poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get('poster_path') else None
            return movie['title'], movie['id'], poster_url
    except Exception as e:
        logger.error(f"Error fetching movie from Supabase: {e}")
    return None, None, None

def download_movie_poster(poster_url):
    """Downloads movie poster for branding."""
    if not poster_url:
        return None
    logger.info("[*] جاري تحميل بوستر الفيلم الأصلي للغلاف...")
    try:
        res = requests.get(poster_url)
        if res.status_code == 200:
            poster_path = os.path.join(TEMP_DIR, "movie_poster.jpg")
            with open(poster_path, 'wb') as f:
                f.write(res.content)
            return poster_path
    except Exception as e:
        logger.error(f"Error downloading poster: {e}")
    return None

def get_trending_content():
    """Fetches trending content from TMDB (Movies & TV)."""
    logger.info("Fetching trending content from TMDB...")
    if not TMDB_API_KEY:
        raise ValueError("TMDB_API_KEY not found.")
        
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    results = response.json().get("results", [])
    
    if not results:
        raise Exception("No trending content found.")
    
    # Filter for Movie or TV
    valid_results = [r for r in results if r.get('media_type') in ['movie', 'tv']]
    if not valid_results:
        raise Exception("No valid movie/tv content found.")

    # Select random item
    item = random.choice(valid_results[:10])
    title = item.get('title') if item.get('media_type') == 'movie' else item.get('name')
    media_type = item.get('media_type', 'movie')
    
    # Process Genres (Max 2)
    genre_ids = item.get('genre_ids', [])
    found_genres = []
    for gid in genre_ids:
        if gid in GENRE_MAP:
            found_genres.append(GENRE_MAP[gid])
            if len(found_genres) >= 2:
                break
    
    if len(found_genres) == 1:
        genre_ar = found_genres[0]
    elif len(found_genres) >= 2:
        genre_ar = f"{found_genres[0]} و{found_genres[1]}"
    else:
        genre_ar = ""
    
    logger.info(f"Selected {media_type}: {title} ({genre_ar})")
    return item, title, media_type, genre_ar

def download_file_with_retry(url, dest_path, retries=3, backoff=2):
    """Downloads a file with exponential backoff retry logic."""
    for i in range(retries):
        try:
            logger.info(f"Downloading {url} to {dest_path} (Attempt {i+1})...")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
                return True
        except Exception as e:
            logger.warning(f"Download attempt {i+1} failed: {e}")
            if i < retries - 1:
                time.sleep(backoff ** i)
    return False

def get_thumbnail(tmdb_id, title):
    """Enforces cinma.online as primary thumbnail source, fallback to TMDB for poster & metadata."""
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', str(title))
    thumb_path = os.path.join(TEMP_DIR, f"thumb_{safe_title}.jpg")
    overview = None
    
    # 1. Try Cinma.online (Enforced Priority)
    cinma_url = f"https://cinma.online/wp-content/uploads/thumbnails/{tmdb_id}.jpg"
    if download_file_with_retry(cinma_url, thumb_path):
        logger.info(f"Thumbnail sourced from cinma.online for ID {tmdb_id}")
        # Note: Overview still needs to be fetched from Playwright scraper or TMDB
    else:
        logger.warning(f"Thumbnail not found on cinma.online for ID {tmdb_id}. Falling back to TMDB.")
        
    # 2. Fallback to TMDB (Poster & Metadata)
    try:
        # Fetch with Arabic language preference
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&language=ar-SA"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            
            # Fetch Arabic Overview
            overview = data.get('overview')
            if not overview:
                # Fallback to English if Arabic is missing
                logger.warning(f"Arabic overview missing for {tmdb_id}, trying English.")
                en_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}"
                en_data = requests.get(en_url, timeout=10).json()
                overview = en_data.get('overview')

            # Fetch High-Res Poster if thumb_path doesn't exist yet
            if not os.path.exists(thumb_path):
                poster_path = data.get('poster_path')
                if poster_path:
                    # Use original resolution as requested
                    tmdb_url = f"https://image.tmdb.org/t/p/original{poster_path}"
                    if download_file_with_retry(tmdb_url, thumb_path):
                        logger.info(f"High-res poster sourced from TMDB for ID {tmdb_id}")
    except Exception as e:
        logger.error(f"TMDB fallback failed for ID {tmdb_id}: {e}")
        
    return thumb_path if os.path.exists(thumb_path) else None, overview

def generate_script(title, overview, media_type="movie", genre_ar="الدراما", max_duration=None):
    """
    Generates the script using Gemini with Zero Hallucination and Dynamic Genre Inference.
    """
    logger.info(f"Generating script for {media_type} '{title}' ({genre_ar})...")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found.")
        
    media_type_ar = "فيلم" if media_type == "movie" else "مسلسل"
    genre_text = f"{genre_ar} " if genre_ar else ""
    
    if DEBUG_SHORT_VIDEO:
        return f"قصتنا انهاردة عن {media_type_ar} {genre_text}{title} [PAUSE] لمشاهدة ال{media_type_ar} كامل وبدون اعلانات ستجد الرابط في اول تعليق", "Test Caption"
    
    # Zero Hallucination Prompt
    prompt = f"""
    Act as a master storyteller. Create a script for a 60-second video about the {media_type} "{title}".
    
    **CRITICAL RULES (ZERO HALLUCINATION):**
    1. USE ONLY the provided plot details. DO NOT invent characters, subplots, or endings.
    2. If details are sparse, focus on the ATMOSPHERE and THEMES (e.g., suspense, betrayal, hope).
    3. INFER DYNAMIC GENRES: Based on the overview, categorize this into high-retention genres like "Sci-Fi", "Success Story", "Karma", or "Mystery" if applicable.
    
    **Script Structure:**
    - Intro (Strict): Start EXACTLY with: "قِصِّتْنَا اِنَّهَارْدَة عَنْ {media_type_ar} {genre_text}[Arabic Title]..."
    - Body: 130-150 words. Modern Standard Arabic with FULL Diacritics (Tashkeel).
    - Outro (Strict): End EXACTLY with: "لمشاهدت ال{media_type_ar} كامِلُ وبدون اعلانات , ستجد الرابِت في اول تعليِق , مٌشاهدَة ممتعة"
    
    **Language Rules:**
    - NO English letters. Transliterate phonetically (e.g., "Matrix" -> "مَاتْرِكْس").
    - Full diacritics on ALL names and foreign terms.
    
    **Caption:** White Egyptian Dialect, high-suspense, includes #سينما_أونلاين.
    
    **Context:** {overview}
    
    Output JSON: {{"script_body": "...", "caption": "..."}}
    """
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    models = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.5-flash']
    
    for model_name in models:
        try:
            # Use the correct google-genai client structure
            response = client.models.generate_content(
                model=model_name, 
                contents=prompt, 
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(response.text.strip())
            return data["script_body"].strip().replace('*', ''), data["caption"].strip()
        except Exception as e:
            logger.warning(f"{model_name} failed: {e}")
            
    # HARD STOP: If all Gemini models fail, ABORT the process.
    error_msg = "❌ **فشل جودة:** نماذج Gemini (1.5, 1.5, 2.5) لا تستجيب. تم إلغاء الفيديو لمنع نشر محتوى بدون سكريبت."
    logger.critical(error_msg)
    send_telegram_alert(error_msg)
    sys.exit(1) # Fail job in GitHub Actions


def clean_text_for_tts(text):
    """Cleans text for Edge-TTS."""
    # Phonetic Fixes
    text = text.replace("مستوى", "مُسْتَوَى").replace("مستوي", "مُسْتَوَى")
    text = text.replace("اخرى", "أُخْرَى").replace("أخرى", "أُخْرَى")
    
    # Remove markdown/special chars
    text = text.replace('*', '').replace('#', '').replace('-', '')
    text = text.replace('"', '').replace("'", "")
    text = re.sub(r'[^\w\s\u0600-\u06FF\.\,\!\?\،\؛]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def create_silence(duration=0.3):
    """Creates a silent audio clip (reduced to 0.3s to save time)."""
    return AudioArrayClip(np.zeros((int(44100 * duration), 2)), fps=44100)

async def generate_audio(text, output_file, media_type="movie"):
    """Generates audio using Alibaba CosyVoice with Edge-TTS fallback."""
    logger.info("Generating audio (Prioritizing Alibaba CosyVoice)...")
    text_cleaned = re.sub(r'\[.*?\]', '', text.replace("[PAUSE]", "||PAUSE||"))
    
    # 1. Alibaba CosyVoice Integration
    if ALIBABA_API_KEY:
        retry_delays = [5, 10, 15] # 3 Attempts
        for delay in retry_delays:
            try:
                logger.info(f"Attempting Alibaba CosyVoice-V3-Plus (Retry delay: {delay if delay != 5 else 'Initial'})...")
                dashscope.api_key = ALIBABA_API_KEY
                # Stability Fix: Use Singapore region for GitHub runners
                dashscope.base_http_api_url = 'https://dashscope-intl.ap-southeast-1.aliyuncs.com/api/v1'
                dashscope.base_websocket_api_url = 'wss://dashscope-intl.ap-southeast-1.aliyuncs.com/api-ws/v1'
                
                # Increase websocket timeout to 30s as requested
                synthesizer = SpeechSynthesizer(
                    model="cosyvoice-v3-plus", 
                    voice="longxiaomiao_v2"
                )
                
                # Alibaba handles the full text better
                alibaba_text = text_cleaned.replace("||PAUSE||", " ، ")
                
                # Use websocket_timeout parameter in call() for stability
                audio_data = synthesizer.call(alibaba_text) # Removed websocket_timeout due to SDK incompatibility
                
                if audio_data:
                    with open(output_file, 'wb') as f:
                        f.write(audio_data)
                    
                    # Verify file
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                        clip = AudioFileClip(output_file)
                        duration = clip.duration
                        clip.close()
                        logger.info(f"Successfully generated Alibaba audio ({duration:.2f}s)")
                        return duration
                    else:
                        logger.warning("Alibaba generated empty or small file.")
                else:
                    logger.warning("Alibaba call returned no data.")
                
            except Exception as e:
                logger.warning(f"Alibaba API attempt failed: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        else:
            logger.error("All 3 Alibaba attempts failed.")
            logger.warning("⚠️ CRITICAL QUALITY FALLBACK: Alibaba failed. Using Edge-TTS as last resort to save the video.")
            # Reset dashscope urls for any future attempts (though we are falling back now)
            dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
            dashscope.base_websocket_api_url = 'wss://dashscope-intl.aliyuncs.com/api-ws/v1'
    else:
        logger.warning("ALIBABA_API_KEY not found. Using Edge-TTS.")

    # 2. Edge-TTS Fallback Logic
    logger.info("Generating audio (Edge-TTS Fallback - Hamdan)...")
    parts = text_cleaned.split("||PAUSE||")
    
    audio_clips = []
    temp_files = []
    current_voice = "ar-EG-HamdanNeural" # High quality last resort voice
    
    try:
        segment_counter = 0
        for part in parts:
            clean_seg = clean_text_for_tts(part)
            if not clean_seg: continue
            
            segment_counter += 1
            temp_filename = f"{TEMP_DIR}/seg_{segment_counter}_{int(datetime.now().timestamp())}.mp3"
            
            # Retry Loop
            success = False
            for _ in range(3):
                try:
                    communicate = edge_tts.Communicate(clean_seg, current_voice)
                    await communicate.save(temp_filename)
                    if os.path.exists(temp_filename) and os.path.getsize(temp_filename) >= 100:
                        success = True
                        break
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"TTS Error: {e}")
                    await asyncio.sleep(1)
            
            if success:
                temp_files.append(temp_filename)
                try:
                    clip = AudioFileClip(temp_filename)
                    if clip.duration > 0:
                        audio_clips.append(clip)
                        audio_clips.append(create_silence(0.3))
                except Exception as e:
                    logger.warning(f"Audio load error: {e}")

        if not audio_clips:
            logger.error("No audio generated by fallback.")
            return 0

        final_audio = concatenate_audioclips(audio_clips)
        final_audio.write_audiofile(output_file)
        duration = final_audio.duration
        final_audio.close()
        return duration
        
    finally:
        for f in temp_files:
            try: os.remove(f)
            except: pass

def get_word_timestamps(audio_file):
    """Extracts timestamps using Whisper."""
    logger.info("Extracting timestamps...")
    try:
        whisper_lib = get_whisper()
        model = whisper_lib.load_model("tiny")
        result = model.transcribe(audio_file, word_timestamps=True)
        words = []
        for segment in result["segments"]:
            for word in segment["words"]:
                words.append({
                    "word": word["word"].strip(),
                    "start": word["start"],
                    "end": word["end"]
                })
        return words
    except Exception as e:
        logger.error(f"Whisper failed: {e}")
        return [{"word": "Error", "start": 0.0, "end": 1.0}]

# -----------------------------------------------------------------------------
# Video Fetching & Processing
# -----------------------------------------------------------------------------

def fallback_download_youtube(youtube_url, output_path):
    """Global Fallback: Downloads video using Invidious API to bypass datacenter blocks."""
    logger.info(f"[Invidious] Attempting global fallback for: {youtube_url}")
    
    # Extract Video ID
    video_id = None
    if "v=" in youtube_url:
        video_id = youtube_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in youtube_url:
        video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
    elif "youtube.com/shorts/" in youtube_url:
        video_id = youtube_url.split("shorts/")[1].split("?")[0]
    
    if not video_id:
        logger.error("[Invidious] Could not extract video ID")
        return None

    # Public Invidious Instances (Ordered by reliability for GitHub Runners)
    instances = [
        f"https://vid.puffyan.us/api/v1/videos/{video_id}",
        f"https://inv.vern.cc/api/v1/videos/{video_id}",
        f"https://invidious.nerdvpn.de/api/v1/videos/{video_id}"
    ]

    for instance_api in instances:
        try:
            logger.info(f"[Invidious] Fetching metadata from: {instance_api}")
            res = requests.get(instance_api, timeout=20)
            res.raise_for_status()
            data = res.json()
            
            # Search for a suitable stream
            streams = data.get("formatStreams", [])
            selected_stream = None
            
            # Priority: 720p mp4 > 360p mp4
            for resolution in ["720p", "360p"]:
                for s in streams:
                    if s.get("resolution") == resolution and "mp4" in s.get("container", "").lower():
                        selected_stream = s
                        break
                if selected_stream: break
            
            if not selected_stream:
                logger.warning(f"[Invidious] No suitable MP4 stream found on {instance_api}")
                continue
            
            stream_url = selected_stream.get("url")
            logger.info(f"[Invidious] Downloading {selected_stream.get('resolution')} stream...")
            
            # Download the stream
            with requests.get(stream_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                logger.info(f"[Invidious] Successfully downloaded to {output_path}")
                return output_path
            
        except Exception as e:
            logger.error(f"[Invidious] Instance {instance_api} failed: {e}")
            
    return None

def fetch_tier1_trailer(movie_title, duration=58, tmdb_id=None, trailer_url=None):
    """
    Fetches official trailer via YT-DLP with capped retries and mobile spoofing.
    STRICT MODE: Exits if trailer fails.
    """
    attempt = 0
    # Fixed Backoff Configuration - 10s per user request
    wait_time = 10
    max_attempts = 3
    
    # Cache for search results to avoid re-searching
    cached_search_results = []
    
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"[Trailer] Attempt {attempt}/{max_attempts} for: {movie_title}")
        
        # Try fetching trailer from TMDB if tmdb_id is available and no trailer_url provided
        # Only on first attempt if we don't have a trailer_url
        if attempt == 1 and not trailer_url and tmdb_id and tmdb_id != 'N/A':
            try:
                url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={TMDB_API_KEY}"
                res = requests.get(url).json()
                videos = res.get('results', [])
                for v in videos:
                    if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
                        trailer_url = f"https://www.youtube.com/watch?v={v.get('key')}"
                        logger.info(f"Found TMDB trailer: {trailer_url}")
                        break
            except Exception as e:
                logger.warning(f"TMDB trailer fetch failed: {e}")

        # Determine strategy
        current_video_url = None
        use_search = False
        
        if trailer_url and attempt == 1:
            current_video_url = trailer_url
        else:
            use_search = True
        
        # Sanitize unique_id to avoid directory creation or invalid chars
        safe_tmdb_id = re.sub(r'[^a-zA-Z0-9]', '_', str(tmdb_id)) if tmdb_id else 'NO_ID'
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', str(movie_title))
        
        unique_id = f"{safe_tmdb_id}_{int(time.time())}"
        raw_filename = f"movie_raw_{unique_id}"
        cut_filename = f"movie_clip_{unique_id}.mp4"
        
        ydl_opts = {
            'cookiefile': 'cookies.txt',
            'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{TEMP_DIR}/{raw_filename}.%(ext)s',
            'quiet': True,
            'nocheckcertificate': True,
            'retries': 3,
            'socket_timeout': 30,
            'merge_output_format': 'mp4',
            'extractor_args': {'youtube': {'client': ['android', 'ios', 'web']}},
            'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        }
        
        try:
            if use_search:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if not cached_search_results:
                        # Search for 10 results to have enough for retries
                        logger.info(f"Searching YouTube for trailer: {movie_title}")
                        search_query = f"ytsearch10:{movie_title} Official Trailer"
                        info = ydl.extract_info(search_query, download=False)
                        cached_search_results = info.get('entries', [])
                        
                    if not cached_search_results:
                         raise ValueError(f"No trailer found for {movie_title}")
                    
                    search_idx = attempt - 1
                    if trailer_url:
                        search_idx -= 1 # Offset because attempt 1 used trailer_url
                        
                    if search_idx < 0: search_idx = 0 # Safety
                    
                    if search_idx < len(cached_search_results):
                        current_video_url = cached_search_results[search_idx]['webpage_url']
                    else:
                        # Fallback if we ran out of results
                        current_video_url = cached_search_results[0]['webpage_url']
                        
            logger.info(f"Downloading video from: {current_video_url}")
            
            # Primary Method: YT-DLP
            try:
                # Use Rich Progress Bar
                download_with_rich(ydl_opts, [current_video_url])
                
                # Robust file finding using glob
                potential_files = glob.glob(os.path.join(TEMP_DIR, f"{raw_filename}*"))
                if not potential_files:
                     raise ValueError(f"Download failed for {movie_title} (No file found)")
                
                input_file = potential_files[0] # Take the first match
                # Prefer .mp4 if multiple exist
                for p in potential_files:
                    if p.endswith(".mp4"):
                        input_file = p
                        break
            except Exception as yt_err:
                logger.warning(f"Primary YT-DLP download failed: {yt_err}")
                if "youtube.com" in current_video_url or "youtu.be" in current_video_url:
                    logger.info("Attempting Invidious API Fallback...")
                    # Fallback Method: Invidious
                    raw_path = os.path.join(TEMP_DIR, f"{raw_filename}.mp4")
                    input_file = fallback_download_youtube(current_video_url, raw_path)
                    
                    if not input_file:
                        raise ValueError(f"Both YT-DLP and Invidious fallback failed for {movie_title}")
                else:
                    raise ValueError(f"Primary YT-DLP download failed for non-YouTube URL: {yt_err}")

            if not input_file or not os.path.exists(input_file):
                raise ValueError(f"Download failed for {movie_title}")

            # Use FFmpeg directly to cut and fix metadata (No MoviePy)
            cut_path = os.path.join(TEMP_DIR, cut_filename)
            
            logger.info(f"Cutting video with FFmpeg (Copy Mode): {input_file} -> {cut_path}")
            
            # Rich Spinner for FFmpeg
            with console.status("[bold green]Cutting Trailer with FFmpeg...[/bold green]"):
                # Use stream copy for speed and stability, remove audio, skip 10s
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", "10",
                    "-i", input_file,
                    "-t", str(duration),
                    "-an",                # Remove audio completely
                    "-c:v", "copy",       # Copy video stream without re-encoding
                    cut_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if not os.path.exists(cut_path):
                 raise ValueError("FFmpeg failed to create output file")
            
            # Verify file size
            file_size = os.path.getsize(cut_path)
            logger.info(f"Cut file created. Size: {file_size} bytes")
            if file_size < 1000:
                raise ValueError(f"Cut file is too small ({file_size} bytes), likely corrupted.")
            
            return cut_path

        except Exception as e:
            logger.error(f"Trailer fetch error (Attempt {attempt}): {e}")
            logger.error(f"Actual Trailer Error: {traceback.format_exc()}")
            
        # If we reach here, the attempt failed
        if attempt < max_attempts:
            logger.info(f"Waiting {wait_time} seconds before next attempt...")
            
            # Rich Countdown Timer
            with get_progress_manager() as progress:
                 task = progress.add_task(f"[yellow]Retrying in {wait_time}s...", total=wait_time, filename="Countdown")
                 for _ in range(wait_time):
                     time.sleep(1)
                     progress.update(task, advance=1)
    
    # All attempts failed - STRICT MODE: ABORT & ALERT
    error_msg = f"❌ **توقف طارئ:** فشل في تحميل إعلان فيلم/مسلسل {movie_title} من يوتيوب. تم إلغاء صناعة الفيديو."
    logger.critical(error_msg)
    
    # 1. Send Telegram Alert
    send_telegram_alert(error_msg)
    
    # 2. Send Email Alert
    send_error_email(
        "CRITICAL: Trailer Fetch Failed", 
        f"The bot failed to download a trailer for '{movie_title}' after {max_attempts} attempts.\n"
        "As per strict quality requirements, the video creation has been aborted to prevent trailer-less content."
    )
    
    # 3. Graceful Exit (sys.exit(0) for GitHub Actions success)
    logger.info("Exiting gracefully to prevent low-quality video generation.")
    sys.exit(0)

def get_video_content(item, title, duration, tmdb_id=None, trailer_url=None):
    """Orchestrates video fetching. STRICT MODE: Only Trailer."""
    return fetch_tier1_trailer(title, duration=duration, tmdb_id=tmdb_id, trailer_url=trailer_url)

def load_viral_queue():
    if os.path.exists(VIRAL_QUEUE_FILE):
        try:
            with open(VIRAL_QUEUE_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {"tracking": {}, "blacklist": []}
                data = json.loads(content)
                
                # Migrate or Fix Structure
                new_data = {"tracking": {}, "blacklist": []}
                
                # If it's the new structure, keep it
                if "tracking" in data:
                    new_data["tracking"] = data["tracking"]
                if "blacklist" in data:
                    new_data["blacklist"] = data["blacklist"]
                
                # If it was the OLD structure, we ignore pending_urls etc.
                # but we might want to keep the blacklist if it's valid.
                # Actually, per user request to "stop aggressive blacklisting", 
                # let's clear the blacklist if we are in this migration phase
                # to give URLs another chance with the multi-strategy logic.
                if "pending_urls" in data or "active_url" in data:
                    logger.info("Old viral queue structure detected. Migrating and clearing blacklist.")
                    new_data["blacklist"] = [] 
                
                return new_data
        except Exception as e:
            logger.error(f"Error loading viral queue: {e}")
    return {"tracking": {}, "blacklist": []}

def save_viral_queue(data):
    try:
        with open(VIRAL_QUEUE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving viral queue: {e}")

def get_yt_duration(url):
    """Fetches total duration using multi-strategy yt-dlp metadata extraction."""
    strategies = [
        ("Default", {}),
        ("Android", {'youtube': {'player_client': ['android']}}),
        ("TV", {'youtube': {'player_client': ['tv']}})
    ]
    
    for name, extractor_args in strategies:
        try:
            print(f"--- Strategy {name} Attempt for {url} Duration ---")
            logger.info(f"--- Strategy {name} Attempt for {url} Duration ---")
            ydl_opts = {
                'cookiefile': 'cookies.txt',
                'quiet': False,
                'no_warnings': False,
                'extract_flat': True,
                'skip_download': True,
            }
            if extractor_args:
                ydl_opts['extractor_args'] = extractor_args
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = float(info.get('duration', 0))
                if duration > 0:
                    print(f"--- Strategy {name} Success! Duration: {duration} ---")
                    logger.info(f"--- Strategy {name} Success! Duration: {duration} ---")
                    return duration
        except Exception as e:
            print(f"--- Strategy {name} Failed: {e} ---")
            logger.warning(f"Strategy {name} failed for {url} duration: {e}")
            continue
            
    print(f"--- All duration fetch strategies failed for {url} ---")
    logger.error(f"All duration fetch strategies failed for {url}")
    return 0

def download_viral_chunk(duration=20):
    """
    Slices viral content with Smart Slicing and robust error handling.
    """
    queue = load_viral_queue()
    
    # 1. Load available URLs
    if os.path.exists(VIRAL_LINKS_FILE):
        try:
            with open(VIRAL_LINKS_FILE, 'r', encoding='utf-8') as f:
                all_urls = [line.strip() for line in f if line.strip().startswith("http")]
        except Exception as e:
            logger.error(f"Failed to read viral_links.txt: {e}")
            all_urls = []
    else:
        logger.error(f"{VIRAL_LINKS_FILE} not found!")
        all_urls = []

    # Filter out blacklisted URLs
    available_urls = [u for u in all_urls if u not in queue.get("blacklist", [])]
    
    if not available_urls:
        raise RuntimeError("All viral URLs failed or are exhausted. Please add new links.")

    # 2. Iterate through URLs safely
    for url in available_urls:
        logger.info(f"Processing viral URL: {url}")
        
        try:
            # Get current progress
            used_seconds = queue["tracking"].get(url, 0)
            
            # Fetch total duration (Metadata only)
            total_duration = get_yt_duration(url)
            
            # Condition A: Exhausted (ONLY blacklist if we know for sure it's exhausted)
            if total_duration > 0 and (total_duration - used_seconds < duration):
                logger.info(f"URL exhausted ({used_seconds}/{total_duration}s). Blacklisting.")
                if url not in queue["blacklist"]:
                    queue["blacklist"].append(url)
                save_viral_queue(queue)
                continue
            
            # Condition B: Valid - Attempt Download & Extraction with multi-strategy
            video_id = url.split("v=")[-1].split("&")[0]
            output_path = f"{TEMP_DIR}/viral_chunk_{video_id}_{int(used_seconds)}.mp4"
            logger.info(f"Extracting clip: {used_seconds}s to {used_seconds + duration}s")

            strategies = [
                ("Default", {}),
                ("Android", {'youtube': {'player_client': ['android']}}),
                ("TV", {'youtube': {'player_client': ['tv']}})
            ]
            
            success = False
            for name, extractor_args in strategies:
                try:
                    print(f"--- Strategy {name} Attempt for {url} Download ---")
                    logger.info(f"--- Strategy {name} Attempt for {url} Download ---")
                    ydl_opts = {
                        'cookiefile': 'cookies.txt',
                        'format': 'bestvideo[ext=mp4][vcodec^=avc1]/best[ext=mp4]',
                        'quiet': False,
                        'no_warnings': False,
                        'http_chunk_size': 1048576,
                    }
                    if extractor_args:
                        ydl_opts['extractor_args'] = extractor_args
                        
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        try:
                            info = ydl.extract_info(url, download=False)
                        except Exception as e:
                            if ("youtube.com" in url or "youtu.be" in url) and name == strategies[-1][0]:
                                logger.warning(f"YT-DLP exhausted all strategies for {url}. Attempting Invidious fallback...")
                                fallback_path = fallback_download_youtube(url, output_path)
                                if fallback_path:
                                    success = True
                                    break
                            raise e

                        if info.get('is_live'):
                            print(f"--- URL is a livestream, skipping: {url} ---")
                            logger.warning(f"URL is a livestream, skipping: {url}")
                            break # Skip this URL entirely if it's a live stream
                            
                        stream_url = info.get('url')
                        if not stream_url:
                            formats = info.get('formats', [])
                            valid_formats = [f for f in formats if f.get('ext') == 'mp4' and 'avc1' in f.get('vcodec', '') and f.get('url')]
                            if not valid_formats:
                                valid_formats = [f for f in formats if f.get('ext') == 'mp4' and f.get('url')]
                            if valid_formats:
                                stream_url = valid_formats[-1]['url']
                                
                        if not stream_url:
                            print(f"--- No stream URL found in strategy {name} ---")
                            logger.warning(f"No stream URL found in strategy {name}")
                            if ("youtube.com" in url or "youtu.be" in url) and name == strategies[-1][0]:
                                logger.info("Attempting Invidious fallback due to no stream URL...")
                                fallback_path = fallback_download_youtube(url, output_path)
                                if fallback_path:
                                    success = True
                                    break
                            continue

                        print(f"--- Strategy {name} Extraction Start ---")
                        cut_cmd = [
                            "ffmpeg", "-y",
                            "-ss", str(used_seconds),
                            "-t", str(duration),
                            "-i", stream_url,
                            "-map", "0:v:0",
                            "-c:v", "copy",
                            "-an",
                            "-f", "mp4",
                            "-movflags", "+faststart",
                            output_path
                        ]
                        
                        result = subprocess.run(cut_cmd, capture_output=True)
                        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
                            # Verify if file is corrupted using OpenCV (lighter than MoviePy)
                            cap = cv2.VideoCapture(output_path)
                            if cap.isOpened():
                                ret, frame = cap.read()
                                if ret:
                                    logger.info(f"Extraction successful and verified with OpenCV: {output_path}")
                                    queue["tracking"][url] = used_seconds + duration
                                    save_viral_queue(queue)
                                    cap.release()
                                    return output_path
                                else:
                                    logger.warning(f"Extracted file is empty or corrupted: {output_path}")
                            else:
                                logger.warning(f"Could not open extracted file: {output_path}")
                            
                            cap.release()
                            try: os.remove(output_path)
                            except: pass
                        else:
                            err_msg = result.stderr.decode(errors='ignore') if result.stderr else "Unknown error"
                            print(f"--- Strategy {name} FFmpeg failed: {err_msg} ---")
                            logger.warning(f"Strategy {name} FFmpeg failed: {err_msg}")
                            if ("youtube.com" in url or "youtu.be" in url) and name == strategies[-1][0]:
                                logger.info("Attempting Invidious fallback due to FFmpeg failure...")
                                # For viral chunks, we need to cut it. fallback_download_youtube downloads full video.
                                # We can download full then cut.
                                full_temp = f"{TEMP_DIR}/full_fallback_{video_id}.mp4"
                                if fallback_download_youtube(url, full_temp):
                                    cut_cmd[6] = full_temp # Use downloaded file instead of stream_url
                                    result = subprocess.run(cut_cmd, capture_output=True)
                                    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
                                        logger.info("Invidious fallback + FFmpeg cut successful.")
                                        queue["tracking"][url] = used_seconds + duration
                                        save_viral_queue(queue)
                                        try: os.remove(full_temp)
                                        except: pass
                                        return output_path
                                try: os.remove(full_temp)
                                except: pass
                            continue
                            
                except Exception as e:
                    print(f"--- Strategy {name} Download Failed: {e} ---")
                    logger.warning(f"Strategy {name} failed for {url}: {e}")
                    if ("youtube.com" in url or "youtu.be" in url) and name == strategies[-1][0]:
                        logger.info("Attempting Invidious fallback after all strategies failed...")
                        full_temp = f"{TEMP_DIR}/full_fallback_{video_id}.mp4"
                        if fallback_download_youtube(url, full_temp):
                             # Need to cut it
                             cut_cmd = [
                                "ffmpeg", "-y",
                                "-ss", str(used_seconds),
                                "-t", str(duration),
                                "-i", full_temp,
                                "-map", "0:v:0",
                                "-c:v", "copy",
                                "-an",
                                "-f", "mp4",
                                "-movflags", "+faststart",
                                output_path
                            ]
                             result = subprocess.run(cut_cmd, capture_output=True)
                             if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
                                 logger.info("Invidious fallback + FFmpeg cut successful.")
                                 queue["tracking"][url] = used_seconds + duration
                                 save_viral_queue(queue)
                                 try: os.remove(full_temp)
                                 except: pass
                                 return output_path
                        try: os.remove(full_temp)
                        except: pass
                    continue
            
            print(f"--- All download strategies failed for {url} ---")
            logger.warning(f"All strategies failed for {url}. Moving to next URL without blacklisting.")
            continue

        except Exception as e:
            logger.warning(f"Unexpected error processing {url}: {e}. Moving to next.")
            continue

    # 3. Safety Break: If loop finishes without returning
    raise RuntimeError("All available viral URLs failed to process. Please check your links or internet connection.")

def auto_crop_black_bars(clip):
    """Detects and crops horizontal black bars."""
    logger.info("Auto-detecting black bars...")
    try:
        frame = clip.get_frame(min(clip.duration * 0.1, 2.0))
        gray_rows = frame.mean(axis=2).mean(axis=1)
        threshold = 10
        
        top_crop = 0
        for i, val in enumerate(gray_rows):
            if val > threshold:
                top_crop = i
                break
                
        bottom_crop = len(gray_rows)
        for i in range(len(gray_rows)-1, -1, -1):
            if gray_rows[i] > threshold:
                bottom_crop = i + 1
                break
        
        if top_crop > 0 or bottom_crop < clip.h:
            logger.info(f"Cropping: Top={top_crop}, Bottom={bottom_crop}")
            return clip.cropped(y1=top_crop, y2=bottom_crop)
    except Exception as e:
        logger.warning(f"Auto-crop failed: {e}")
    return clip

def apply_anti_copyright(clip, target_size):
    """Applies Speed 1.01x, Zoom 1.02x."""
    # Speed 1.01x
    clip = clip.with_effects([vfx.MultiplySpeed(1.01)])
    
    # Fit to target size then Zoom 1.02x
    target_w, target_h = target_size
    ratio_clip = clip.w / clip.h
    ratio_target = target_w / target_h
    
    if ratio_clip > ratio_target:
        clip = clip.resized(height=target_h)
    else:
        clip = clip.resized(width=target_w)
        
    # Zoom 1.02x
    clip = clip.with_effects([vfx.Resize(1.02)])
    
    # Center Crop
    clip = clip.cropped(x1=(clip.w - target_w)//2, y1=(clip.h - target_h)//2, width=target_w, height=target_h)
    
    return clip

# --- Branding Helpers ---
def get_font():
    try: return ImageFont.truetype("arial.ttf", FONT_SIZE)
    except: return ImageFont.load_default()

def create_char_image(char, font):
    dummy = Image.new('RGBA', (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), char, font=font)
    w = bbox[2] - bbox[0]
    h = int(FONT_SIZE * 2.5)
    box_w = int(w + STROKE_WIDTH * 4 + 10)
    
    img = Image.new('RGBA', (box_w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    x = box_w // 2
    y = int(h * 0.7)
    
    for adj in range(-STROKE_WIDTH, STROKE_WIDTH+1):
        for adj2 in range(-STROKE_WIDTH, STROKE_WIDTH+1):
             d.text((x+adj, y+adj2), char, font=font, fill=STROKE_COLOR, anchor="mb")
    d.text((x, y), char, font=font, fill=TEXT_COLOR, anchor="mb")
    
    path = f"{TEMP_DIR}/char_{ord(char)}.png"
    img.save(path)
    return path, w + 2, box_w, h, y

def process_arabic_text(text):
    import arabic_reshaper
    from bidi.algorithm import get_display
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

# -----------------------------------------------------------------------------
# Video Assembly
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Video Assembly Helpers
# -----------------------------------------------------------------------------

def get_smart_thumbnail(video_path):
    """Selects the best frame for thumbnail using brightness and Laplacian variance."""
    logger.info("[*] جاري البحث عن أفضل لقطة للغلاف...")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames <= 0:
        logger.warning("Could not get frame count for thumbnail.")
        return None
        
    best_frame = None
    max_score = -1

    # Try 15 random frames in the 'safety zone' (20% to 80%)
    for _ in range(15):
        random_frame = random.randint(int(total_frames * 0.2), int(total_frames * 0.8))
        cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame)
        ret, frame = cap.read()
        if not ret: continue

        # A. Brightness test (avoid black/dark frames)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        if brightness < 50: continue

        # B. Sharpness test (Laplacian variance)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if score > max_score:
            max_score = score
            best_frame = frame

    cap.release()
    
    if best_frame is not None:
        thumb_path = os.path.join(TEMP_DIR, "raw_thumb.jpg")
        cv2.imwrite(thumb_path, best_frame)
        return thumb_path
    return None

def apply_branding_to_thumb(image_path, movie_title):
    """Applies branding and movie title to the thumbnail."""
    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Load logo for branding
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            logo_img = Image.open(logo_path).convert("RGBA")
            # Resize logo (e.g., width 300)
            aspect = logo_img.height / logo_img.width
            new_w = 300
            new_h = int(new_w * aspect)
            logo_img = logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # Paste logo top-left
            img.paste(logo_img, (50, 50), logo_img)
            
        # Add Movie Title (centered bottom)
        # We'll use a simple fallback if font fails
        try:
            font = ImageFont.truetype("arial.ttf", 80)
        except:
            font = ImageFont.load_default()
            
        text = movie_title.upper()
        # Use textbbox for newer Pillow versions
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        # Draw background strip for text
        draw.rectangle([0, img.height - th - 100, img.width, img.height], fill=(0,0,0,150))
        draw.text(((img.width - tw)//2, img.height - th - 50), text, font=font, fill="white")
        
        final_thumb = os.path.join(OUTPUT_DIR, "final_thumbnail.jpg")
        img.save(final_thumb)
        return final_thumb
    except Exception as e:
        logger.error(f"Error applying branding to thumb: {e}")
        return image_path

def create_reel(video_path, audio_path, words, output_path, movie_title_en="", poster_path=None):
    """Assembles the final video with 60/40 split and movie title on divider."""
    logger.info("Assembling Reel (60/40 Split)...")
    
    # Load Audio
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    
    clips_to_composite = []
    
    # --- Top Screen (60%, 1080x1152) ---
    logger.info("Processing Top Screen (60%)...")
    if video_path and os.path.exists(video_path):
        top_clip = VideoFileClip(video_path)
        top_clip = auto_crop_black_bars(top_clip)
        
        if top_clip.duration < total_duration:
            top_clip = top_clip.with_effects([vfx.Loop(duration=total_duration)])
        else:
            top_clip = top_clip.subclipped(0, total_duration)
            
        # Force Stretch Vertically to 1152px (ignoring aspect ratio)
        top_clip = top_clip.with_effects([vfx.Resize(new_size=(1080, 1152))])
        
        # Anti-Copyright Effects
        top_clip = top_clip.with_effects([vfx.MultiplySpeed(1.01)])
        top_clip = top_clip.with_effects([vfx.Resize(1.02)])
        
        # Crop back to 1080x1152
        w_final, h_final = 1080, 1152
        top_clip = top_clip.cropped(
            x1=(top_clip.w - w_final)//2, 
            y1=(top_clip.h - h_final)//2, 
            width=w_final, 
            height=h_final
        )
        
        top_clip = top_clip.with_position((0, 0))
        clips_to_composite.append(top_clip)
    else:
        logger.warning("No video path found for Top Screen.")
        clips_to_composite.append(ColorClip(size=(1080, 1152), color=(0,0,0), duration=total_duration).with_position((0,0)))

    # --- Bottom Screen (40%, 1080x768) ---
    logger.info("Processing Bottom Screen (40%)...")
    viral_path = download_viral_chunk(total_duration)
    
    if viral_path and os.path.exists(viral_path):
        bot_clip = VideoFileClip(viral_path).without_audio()
        if bot_clip.duration < total_duration:
            bot_clip = bot_clip.with_effects([vfx.Loop(duration=total_duration)])
        else:
            bot_clip = bot_clip.subclipped(0, total_duration)
            
        bot_clip = apply_anti_copyright(bot_clip, (1080, 768))
        bot_clip = bot_clip.with_position((0, 1152))
        clips_to_composite.append(bot_clip)
    else:
        logger.warning("No viral video found for Bottom Screen.")
        clips_to_composite.append(ColorClip(size=(1080, 768), color=(20,20,20), duration=total_duration).with_position((0,1152)))

    # --- Logo ---
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        logo_img = Image.open(logo_path).convert("RGBA")
        logo_np = np.array(logo_img)
        logo = ImageClip(logo_np, transparent=True)
        logo = (logo.with_duration(total_duration)
                .with_effects([vfx.Resize(width=225)]) 
                .with_position((10, 30)))
        clips_to_composite.append(logo)
    else:
        logger.warning(f"Logo not found at {logo_path}")

    # --- Website Image (website.png) ---
    website_img_path = "website.png"
    website_clip = None
    if os.path.exists(website_img_path):
        try:
            web_img = Image.open(website_img_path).convert("RGBA")
            web_np = np.array(web_img)
            website_clip = (ImageClip(web_np, transparent=True)
                            .with_duration(total_duration)
                            .with_effects([vfx.Resize(width=int(1080 * 0.7))])
                            .with_position(('center', 0.93), relative=True))
        except Exception as e:
            logger.error(f"Error adding website image: {e}")
    else:
        logger.warning(f"website.png not found at {website_img_path}")

    # --- Composite final video with correct layer order ---
    # Append critical overlays at the VERY END to ensure they are on top
    if website_clip:
        clips_to_composite.append(website_clip)
        logger.info("Added website.png overlay at bottom center")

    logger.info("Rendering final video...")
    with console.status("[bold red]Rendering Final Reel...[/bold red]"):
        final = CompositeVideoClip(clips_to_composite, size=(1080, 1920))
        voiceover_audio = audio_clip
        mixed_audio = voiceover_audio
        final = final.with_audio(mixed_audio)
        
        # Ensure output_path is strictly a string
        if not isinstance(output_path, str):
            output_path = str(output_path)
            
        final.write_videofile(output_path, fps=30, codec='libx264', audio_codec='aac', threads=4)
    
   # Cleanup
    final.close()
    audio_clip.close()
    
    # Explicitly close sub-clips to release file handles on Windows
    for clip in clips_to_composite:
        try:
            clip.close()
        except:
            pass
            
    if viral_path:
        try:
            os.remove(viral_path)
        except Exception as e:
            logger.warning(f"Could not remove viral temp file: {e}")

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def reply_to_comments(page_id, access_token):
    """
    Fetches recent comments and replies to questions about the movie name using Gemini.
    """
    logger.info("Checking for new comments to reply to...")
    try:
        # 1. Get Page Posts (limit 5) with message and comments
        url_posts = f"https://graph.facebook.com/v19.0/{page_id}/posts?fields=id,message,comments{{id,message,from,can_comment}}&limit=5&access_token={access_token}"
        res = requests.get(url_posts).json()
        
        if 'error' in res:
            logger.error(f"FB Graph API Error (Posts): {res['error']}")
            return

        posts = res.get('data', [])
        for post in posts:
            post_id = post.get('id')
            post_message = post.get('message', '')
            comments_data = post.get('comments', {}).get('data', [])
            
            # Extract Movie Name from Post Message (Hashtags)
            # Pattern: #فيلم_Name_Here or just English name in hashtags
            movie_name_context = "Unknown Movie"
            if post_message:
                # Try to find #فيلم_...
                match = re.search(r'#فيلم_([^\s#]+)', post_message)
                if match:
                    movie_name_context = match.group(1).replace('_', ' ')
                else:
                    # Fallback: look for English chars at the end or just use the whole message as context
                    movie_name_context = post_message[:200] # Use first 200 chars as context

            if not comments_data:
                continue

            for comment in comments_data:
                comment_id = comment.get('id')
                comment_text = comment.get('message', '')
                sender_id = comment.get('from', {}).get('id')
                
                # Skip own comments (Page ID check)
                if sender_id == page_id:
                    continue
                
                # Skip if already replied (Naive check: FB API doesn't give 'is_replied' easily in this view)
                # To avoid spamming, we will rely on a local check or just process 'latest' 
                # Ideally we need a DB. For now, we will just use Gemini to check intent 
                # AND maybe check if we can fetch replies-to-comment. 
                # fetching replies to comment: /comment_id/comments
                
                # CHECK IF WE ALREADY REPLIED
                # We need to fetch sub-comments of this comment
                url_replies = f"https://graph.facebook.com/v19.0/{comment_id}/comments?access_token={access_token}"
                replies_res = requests.get(url_replies).json()
                replies = replies_res.get('data', [])
                already_replied = False
                for r in replies:
                    if r.get('from', {}).get('id') == page_id:
                        already_replied = True
                        break
                
                if already_replied:
                    continue

                # ANALYZE INTENT WITH GEMINI
                if not GEMINI_API_KEY: continue
                
                logger.info(f"Analyzing comment for reply: {comment_text}")
                genai_lib = get_genai()
                genai_lib.configure(api_key=GEMINI_API_KEY)
                model = genai_lib.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                Analyze this Facebook comment: "{comment_text}"
                Context: The post is about the movie "{movie_name_context}".
                
                Does the user want to know the movie name or the link?
                Reply ONLY with JSON: {{"needs_reply": true/false, "reply_text_ar": "..."}}
                
                If true:
                Generate a fun, smart, short Arabic reply (Egyptian dialect). 
                Include the movie name "{movie_name_context}" if known.
                Tell them the link is in the first comment or use "https://cinma.online".
                Example: "اسم الفيلم {movie_name_context} يا غالي! والرابط في أول تعليق مشاهدة ممتعة �"
                """
                
                try:
                    response = model.generate_content(prompt)
                    # Clean json
                    text_resp = response.text.strip()
                    if text_resp.startswith("```json"):
                        text_resp = text_resp[7:-3]
                    
                    data = json.loads(text_resp)
                    
                    if data.get("needs_reply"):
                        reply_text = data.get("reply_text_ar")
                        if reply_text:
                            # POST REPLY
                            logger.info(f"Replying to comment {comment_id}: {reply_text}")
                            if not SIMULATION_MODE:
                                url_post_reply = f"https://graph.facebook.com/v19.0/{comment_id}/comments"
                                payload = {'message': reply_text, 'access_token': access_token}
                                reply_res = requests.post(url_post_reply, data=payload).json()
                                if 'error' in reply_res:
                                    logger.error(f"FB Comment Reply Failed: {json.dumps(reply_res, indent=4)}")
                                    logger.error(f"Graph API Error Code: {reply_res.get('error', {}).get('code')}")
                                else:
                                    logger.info(f"Successfully replied to comment {comment_id}")
                            else:
                                logger.info(f"[SIMULATION] Would reply: {reply_text}")
                                
                except Exception as e:
                    logger.warning(f"Gemini Comment Analysis failed: {e}")
                    continue

    except Exception as e:
        logger.error(f"Comment Reply Error: {e}")

def upload_to_facebook(video_path, thumb_path, caption, comment_text, page_id, access_token, content_id=None):
    """
    Uploads a video to Facebook Reels using the Graph API with Polling.
    """
    logger.info(f"Starting Facebook Reel upload: {video_path}")
    
    try:
        # 1. Initialize
        init_res = requests.post(f"https://graph.facebook.com/v19.0/{page_id}/video_reels", 
                                data={'upload_phase': 'start', 'access_token': access_token}).json()
        video_id = init_res.get('video_id')
        if not video_id:
            logger.error(f"FB Init Failed: {json.dumps(init_res, indent=4)}")
            return False
            
        # 2. Upload Binary
        upload_url = f"https://rupload.facebook.com/video-reels/{video_id}"
        headers = {
            'Authorization': f'OAuth {access_token}',
            'offset': '0',
            'file_size': str(os.path.getsize(video_path)),
            'Content-Type': 'application/octet-stream'
        }
        with open(video_path, 'rb') as f:
            upload_res = requests.post(upload_url, data=f, headers=headers).json()
            if 'error' in upload_res:
                logger.error(f"FB Binary Upload Failed: {json.dumps(upload_res, indent=4)}")
                return False
            
        # 3. Publish
        publish_res = requests.post(f"https://graph.facebook.com/v19.0/{page_id}/video_reels", 
                                   data={
                                       'upload_phase': 'finish',
                                       'video_id': video_id,
                                       'description': caption,
                                       'video_state': 'PUBLISHED',
                                       'access_token': access_token
                                   }).json()
        
        if 'error' in publish_res:
            logger.error(f"FB Publish Failed: {json.dumps(publish_res, indent=4)}")
            logger.error(f"Graph API Error Code: {publish_res.get('error', {}).get('code')}")
            return False
            
        logger.info(f"Reel Published! ID: {video_id}. Polling for status...")
        
        # --- Update Scheduling and Posted ID after Success ---
        update_scheduling(content_id=content_id)
        
        # 4. Polling for Readiness
        for _ in range(10): # Max 5 minutes
            time.sleep(30)
            status_res = requests.get(f"https://graph.facebook.com/v19.0/{video_id}?fields=status&access_token={access_token}").json()
            if 'error' in status_res:
                logger.error(f"FB Status Poll Failed: {json.dumps(status_res, indent=4)}")
                continue
            status = status_res.get('status', {}).get('video_status')
            logger.info(f"Video Status: {status}")
            if status == 'ready':
                break
        
        # 5. Delayed Comment
        if comment_text:
            time.sleep(20) # Extra buffer
            comment_res = requests.post(f"https://graph.facebook.com/v19.0/{video_id}/comments", 
                         data={'message': comment_text, 'access_token': access_token}).json()
            if 'error' in comment_res:
                logger.error(f"FB First Comment Failed: {json.dumps(comment_res, indent=4)}")
            else:
                logger.info("First comment added successfully.")
            
        return True
    except Exception as e:
        logger.error(f"FB Upload Error: {e}")
        return False

async def run_one_cycle():
    logger.info("--- Starting Cinema Social Bot (LOCKED MODE) ---")
    clean_temp_files()
    audio_path = None
    output_video_path = None
    
    try:
        # 1. Content - New Catalog-driven Selection
        selected_content = await select_best_content()
        if not selected_content:
            msg = "⚠️ لم يتم العثور على محتوى جديد في Supabase (تم نشر كل شيء). بانتظار إضافة أفلام جديدة..."
            logger.warning(msg)
            # send_telegram_alert(msg) # Optional: uncomment if you want an alert
            sys.exit(0)

        title = selected_content['Title']
        # Use our own DB ID as movie_id for tracking, but keep tmdb_id for metadata
        content_db_id = selected_content.get('id', selected_content['tmdb_id'])
        movie_id = selected_content['tmdb_id']
        poster_url = selected_content['Poster_URL']
        trailer_url = selected_content['Trailer_URL']
        media_type = selected_content['Type'].lower()
        media_type_ar = "فيلم" if media_type == "movie" else "مسلسل"
        watch_url = selected_content['Watch_URL']
        overview = selected_content.get('overview')
        title_en = title
        
        # Get Arabic Genre from TMDB IDs
        genre_ar = ""
        if selected_content['genre_ids']:
            genre_ar = GENRE_MAP.get(selected_content['genre_ids'][0], "")

        logger.info(f"Processing Catalog Item: {title} ({media_type})")

        # 2. Metadata Fallback (Poster & Metadata Plan B)
        final_thumb, tmdb_overview = get_thumbnail(movie_id, title)
        
        # If overview is missing or empty, use TMDB fallback
        if not overview or len(str(overview).strip()) < 10:
            if tmdb_overview:
                logger.info(f"Using TMDB fallback overview for '{title}'")
                overview = tmdb_overview
            else:
                logger.warning(f"No overview found in Supabase or TMDB for '{title}'")
        
        # Poster for branding (use final_thumb as primary, download_movie_poster as fallback)
        poster_path = final_thumb if final_thumb else (download_movie_poster(poster_url) if poster_url else None)
        
        # 3. Script
        script, caption = generate_script(title, overview, media_type, genre_ar)
        
        # 3. Audio
        audio_path = f"{TEMP_DIR}/voiceover.mp3"
        audio_duration = await generate_audio(script, audio_path, media_type=media_type)
        if audio_duration and audio_duration < 55:
            logger.warning(f"Audio too short ({audio_duration:.1f} seconds), video will be short.")
        
        # 4. Video Generation Check
        # FORCE ENABLE FOR SIMULATION (User Request)
        ENABLE_VIDEO_GENERATION = True 
        
        if ENABLE_VIDEO_GENERATION:
            logger.info("Starting Video Generation...")
            
            # Extract timestamps for subtitles
            words = get_word_timestamps(audio_path)
            
            # Get Video Content (Trailer)
            video_path = get_video_content({}, title, int(audio_duration) if audio_duration else 58, tmdb_id=movie_id, trailer_url=trailer_url)
            
            # Assemble Reel (New Logic)
            output_video_path = f"{OUTPUT_DIR}/final_reel.mp4"
            if not create_reel(video_path, audio_path, words, output_video_path, movie_title_en=title, poster_path=poster_path):
                logger.error("Reel generation failed.")
                return
            
            # 5. Metadata
            final_caption = f"{caption}\n\n#سينما_أونلاين #ترشيحات_أفلام\n{WEBSITE_TEXT}"
            final_comment = f"لمشاهدة ال{media_type_ar} كاملاً وبدون اعلانات:\n{watch_url}"
            
            if SIMULATION_MODE:
                logger.info(f"[SIMULATION] Video: {output_video_path}, Thumb: {final_thumb}")
            else:
                success = upload_to_facebook(output_video_path, final_thumb, final_caption, final_comment, FB_PAGE_ID, FB_PAGE_TOKEN, content_id=content_db_id)
                if success:
                    send_telegram_alert(f"✅ <b>Reel Published!</b>\n\n🎬 <b>Title:</b> {title}\n🆔 <b>DB ID:</b> {content_db_id}\n\n🔗 <a href='{watch_url}'>Watch on Cinma.online</a>")
                else:
                    send_telegram_alert(f"⚠️ <b>Upload Failed!</b>\n\n🎬 <b>Title:</b> {title}\nCheck logs for FB API error details.")
        
        # 6. Reply to Comments (Skipped in Simulation as requested, but logic is there)
        if not SIMULATION_MODE:
             reply_to_comments(FB_PAGE_ID, FB_PAGE_TOKEN)

    except Exception as e:
        logger.error(f"Critical Error: {e}")
        logger.error(traceback.format_exc())
        send_telegram_alert(f"❌ <b>CinemaBot Critical Error</b>\n\n<code>{str(e)}</code>")
        send_error_email("Bot Cycle Crashed", str(e))
    finally:
        # Final cleanup
        if audio_path and os.path.exists(audio_path):
            # Retry delete to avoid Windows file-in-use errors
            for _ in range(5):
                try:
                    os.remove(audio_path)
                    break
                except PermissionError:
                    time.sleep(1)
                except Exception:
                    time.sleep(0.5)
        # Optional: clean_temp_files() # Don't clean immediately so user can inspect output in output/

if __name__ == "__main__":
    try:
        # Check scheduling before starting cycle
        check_scheduling()
        
        asyncio.run(run_one_cycle())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        print(f"Fatal Error: {e}")
