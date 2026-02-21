import os
import random
import requests
import json
import asyncio
import re
import glob
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions
import edge_tts
import yt_dlp
# MoviePy 2.0 Imports
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, ImageClip
import moviepy.video.fx as vfx
import moviepy.audio.fx as afx
from moviepy.audio.AudioClip import CompositeAudioClip

import whisper
import numpy as np
import arabic_reshaper
from bidi.algorithm import get_display

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

"""
--------------------------------------------------------------------------------
HOW TO ADD API KEYS TO GITHUB SECRETS
--------------------------------------------------------------------------------
1. Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions.
2. Click "New repository secret".
3. Add the following secrets:
   - TMDB_API_KEY: Your TMDB API Key.
   - GEMINI_API_KEY: Your Google Gemini API Key.
   - FB_PAGE_TOKEN: Your Facebook Page Access Token (Long-lived recommended).
   - FB_PAGE_ID: Your Facebook Page ID.
--------------------------------------------------------------------------------
"""

# Constants
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
OUTPUT_DIR = "output"
TEMP_DIR = "temp"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 1. Fetch Trending Movie from TMDB
def get_trending_movie():
    logger.info("Fetching trending movie from TMDB...")
    if not TMDB_API_KEY:
        raise ValueError("TMDB_API_KEY not found in environment variables.")
        
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    
    if not results:
        raise Exception("No trending movies found.")
    
    # Pick a random movie from top 5
    movie = random.choice(results[:5])
    logger.info(f"Selected movie: {movie['title']}")
    return movie

# 2. Generate Script with Gemini (with Fallback Mechanism)
def generate_script(movie_title, movie_overview):
    logger.info(f"Generating script for {movie_title} using Gemini...")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found.")
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    # List of models to try in order: Best/Newest -> Stable -> Fallback
    models_to_try = [
        'gemini-2.5-flash',   # Latest fast model
        'gemini-2.0-flash',   # Previous stable fast model
        'gemini-1.5-flash',   # Reliable workhorse
        'gemini-1.5-pro'      # High capacity fallback
    ]
    
    prompt = f"""
    Act as a famous Egyptian content creator (YouTuber/TikToker) who is "Saye3" (street-smart) and funny.
    Write a viral Reels script (under 50 seconds spoken) in **Cairo Slang (Ammiya)** for the movie "{movie_title}".
    
    **Persona & Tone:**
    - You are talking to your friends at a cafe.
    - Use popular Egyptian street slang: "يا جدعان"، "جامد جدي"، "ركز معايا"، "الليلة فيها إن"، "يخرب بيت جماله".
    - **NO Modern Standard Arabic (Fusha).** Strictly Ammiya.
    - Be high energy, dramatic, and suspenseful.
    
    **Structure:**
    1. **The Hook:** A shocking question or statement.
    2. **The Story:** Tell the movie plot like a juicy gossip story.
    3. **CTA:** End exactly with: "وعشان تشوف الفيلم، ادخل على موقع أونلاين سينما (online cinema) وما تنساش اللايك!"
    
    **Formatting Rules:**
    - Write phonetic Arabic for any English names (e.g. "باتمان" not "Batman").
    - Keep sentences short and punchy for the TTS engine.
    - Return ONLY the raw Arabic text.
    """
    
    for model_name in models_to_try:
        try:
            logger.info(f"Attempting to generate script with model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            script = response.text.strip().replace('*', '')
            logger.info(f"Script generated successfully using {model_name}.")
            return script
            
        except exceptions.ResourceExhausted as e:
            logger.warning(f"Resource Exhausted (Quota exceeded) for {model_name}. Switching to fallback...")
            continue # Try next model
        except exceptions.TooManyRequests as e:
            logger.warning(f"Too Many Requests (429) for {model_name}. Switching to fallback...")
            continue # Try next model
        except Exception as e:
            logger.error(f"Unexpected error with {model_name}: {e}")
            # If it's a critical error not related to quota, we might want to continue or break.
            # For robustness, we continue to try other models unless it's an auth error (which would likely fail all).
            if "API_KEY" in str(e): # Stop if key is invalid
                 raise
            continue

    # If loop finishes without returning
    raise RuntimeError("All Gemini models failed to generate the script. Please check quotas or API key.")

# 3. Clean Text for TTS
def clean_text_for_tts(text):
    # Remove markdown and special chars
    text = text.replace('*', '').replace('#', '').replace('-', '')
    text = text.replace('"', '').replace("'", "")
    
    # Remove emojis
    text = re.sub(r'[^\w\s\u0600-\u06FF]', '', text)
    
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 4. Generate Audio with Edge-TTS
async def generate_audio(text, output_file):
    logger.info("Generating audio with Edge-TTS...")
    
    # Clean text before sending to TTS
    clean_text = clean_text_for_tts(text)
    logger.info(f"Cleaned Text for TTS: {clean_text[:50]}...")
    
    voice = "ar-EG-SalmaNeural" # Egyptian Female Voice (Natural & Storytelling style)
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save(output_file)
    logger.info(f"Audio saved to {output_file}")

# 4. Get Word Timestamps using Whisper
def get_word_timestamps(audio_file):
    logger.info("Extracting timestamps with Whisper...")
    # Use 'tiny' model for faster execution on CI
    model = whisper.load_model("tiny")
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

# 5. Get Video Content (3-Tier Fallback System)
def get_video_content(movie, audio_duration):
    movie_title = movie['title']
    movie_id = movie['id']
    logger.info(f"Getting video content for {movie_title}...")
    
    # Tier 1: yt-dlp with Mobile Impersonation
    try:
        logger.info("[Tier 1] Attempting yt-dlp with Mobile Impersonation...")
        search_query = f"{movie_title} official trailer"
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android']}}, # Mobile User Agent
            'nocheckcertificate': True,
            'default_search': 'ytsearch1:', 
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            video_id = info['entries'][0]['id']
            files = glob.glob(f"{TEMP_DIR}/{video_id}.*")
            if files:
                logger.info("[Tier 1] Success: Trailer downloaded.")
                return files[0]
            
    except Exception as e:
        logger.warning(f"[Tier 1] Failed: {e}")

    # Tier 2: Pexels Stock Footage (Cinematic Fallback)
    try:
        logger.info("[Tier 2] Attempting Pexels Stock Footage...")
        if not PEXELS_API_KEY:
            logger.warning("PEXELS_API_KEY not found. Skipping Tier 2.")
            raise ValueError("Missing Pexels API Key")

        # Determine search query based on title or generic keywords
        # We can try searching for the movie title, but Pexels might not have it.
        # Fallback to generic cinematic queries.
        queries = [movie_title + " movie", "cinematic dark", "dramatic film scene", "mystery cinematic"]
        video_url = None
        
        headers = {'Authorization': PEXELS_API_KEY}
        
        for query in queries:
            logger.info(f"Searching Pexels for: {query}")
            search_url = f"https://api.pexels.com/videos/search?query={query}&per_page=3&orientation=portrait&size=medium"
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                videos = data.get('videos', [])
                if videos:
                    # Pick a random video from results
                    video_data = random.choice(videos)
                    video_files = video_data.get('video_files', [])
                    # Sort by quality (width) to get decent quality but not huge
                    video_files.sort(key=lambda x: x['width'], reverse=True)
                    
                    # Find a suitable MP4
                    for vf in video_files:
                        if vf['file_type'] == 'video/mp4':
                            video_url = vf['link']
                            break
                    
                    if video_url:
                        logger.info(f"Found video on Pexels: {video_url}")
                        break
            
        if video_url:
            video_filename = f"{TEMP_DIR}/pexels_video.mp4"
            with requests.get(video_url, stream=True) as r:
                r.raise_for_status()
                with open(video_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info("[Tier 2] Success: Video downloaded via Pexels.")
            return video_filename
        else:
             logger.warning("No suitable videos found on Pexels.")
            
    except Exception as e:
        logger.warning(f"[Tier 2] Failed: {e}")

    # Tier 3: The Ultimate Slideshow Fallback (TMDB Backdrops + Ken Burns Effect)
    try:
        logger.info("[Tier 3] Initiating Ultimate Slideshow Fallback...")
        
        # Fetch Backdrops from TMDB
        images_url = f"https://api.themoviedb.org/3/movie/{movie_id}/images?api_key={TMDB_API_KEY}"
        response = requests.get(images_url)
        response.raise_for_status()
        data = response.json()
        backdrops = data.get('backdrops', [])
        
        if not backdrops:
            # Fallback to posters if no backdrops
            backdrops = data.get('posters', [])
            
        if not backdrops:
             raise Exception("No images found in TMDB.")
             
        # Select top 5-7 images
        selected_images = backdrops[:7]
        image_paths = []
        
        for idx, img_data in enumerate(selected_images):
            img_url = f"https://image.tmdb.org/t/p/original{img_data['file_path']}"
            img_path = f"{TEMP_DIR}/slide_{idx}.jpg"
            
            # Download Image
            with requests.get(img_url, stream=True) as r:
                r.raise_for_status()
                with open(img_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            image_paths.append(img_path)
            
        if not image_paths:
            raise Exception("Failed to download any images.")
            
        # Create Slideshow with Ken Burns Effect
        logger.info(f"Creating slideshow with Ken Burns effect from {len(image_paths)} images...")
        clips = []
        duration_per_slide = audio_duration / len(image_paths)
        
        for idx, img_path in enumerate(image_paths):
            # Create ImageClip
            img_clip = ImageClip(img_path).with_duration(duration_per_slide)
            
            # 1. Resize to cover 1080x1920 (Base static crop)
            w, h = img_clip.size
            target_ratio = 9/16
            
            if w/h > target_ratio:
                img_clip = img_clip.resized(height=1920)
                w_new = img_clip.size[0]
                x_center = w_new / 2
                img_clip = img_clip.cropped(x1=x_center - (1080/2), x2=x_center + (1080/2), y1=0, y2=1920)
            else:
                img_clip = img_clip.resized(width=1080)
                h_new = img_clip.size[1]
                y_center = h_new / 2
                img_clip = img_clip.cropped(x1=0, x2=1080, y1=y_center - (1920/2), y2=y_center + (1920/2))
                
            # 2. Apply Ken Burns Effect (Alternating Zoom In / Zoom Out)
            if idx % 2 == 0:
                # Zoom In: 1.0 -> 1.15
                effect = vfx.Resize(lambda t: 1 + 0.04 * t)
            else:
                # Zoom Out: 1.15 -> 1.0 (Approx)
                effect = vfx.Resize(lambda t: 1.15 - 0.04 * t)
            
            img_clip = img_clip.with_effects([effect])
            
            # 3. Force Center in 1080x1920 Container (to handle the growth from zoom)
            # This ensures the video size stays constant 1080x1920
            img_clip = CompositeVideoClip([img_clip.with_position("center")], size=(1080, 1920))
            
            clips.append(img_clip)
            
        # Concatenate
        slideshow_video = concatenate_videoclips(clips, method="compose")
        slideshow_path = f"{TEMP_DIR}/slideshow_fallback.mp4"
        slideshow_video.write_videofile(slideshow_path, fps=24, codec='libx264')
        
        logger.info("[Tier 3] Success: Slideshow generated.")
        return slideshow_path

    except Exception as e:
        logger.error(f"[Tier 3] Failed: {e}")
        raise RuntimeError("All 3 Tiers of video retrieval failed. System cannot proceed.")

# Helper for Arabic Text
def process_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# Helper to download font
def download_font():
    font_path = f"{TEMP_DIR}/Cairo-Bold.ttf"
    
    # Force remove old font to ensure update
    if os.path.exists(font_path):
        try:
            os.remove(font_path)
            logger.info("Removed existing font file to force update.")
        except OSError:
            pass

    logger.info("Downloading Cairo-Bold font...")
    url = "https://raw.githubusercontent.com/Gueez/Cairo-Font/master/fonts/ttf/Cairo-Bold.ttf"
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(font_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Font downloaded successfully.")
    except Exception as e:
        logger.error(f"Failed to download font: {e}")
        return None # Return None to signal fallback
    return font_path

# 6. Create Video with MoviePy
def create_reel(video_path, audio_path, words, output_path):
    logger.info("Editing video...")
    
    # Ensure font is available
    font_path = download_font()
    
    # Load audio
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    # Load video
    video_clip = VideoFileClip(video_path)
    
    # Loop video if shorter than audio, or cut if longer
    if video_clip.duration < duration:
        # Loop video to match audio duration
        # MoviePy 2.0: Use with_effects for loop
        video_clip = video_clip.with_effects([vfx.Loop(duration=duration)])
    else:
        video_clip = video_clip.subclipped(0, duration)
        
    # Crop to 9:16 (Vertical)
    w, h = video_clip.size
    target_ratio = 9/16
    current_ratio = w/h
    
    if current_ratio > target_ratio:
        # Too wide, crop width
        new_w = int(h * target_ratio)
        x_center = w / 2
        # MoviePy 2.0: cropped() instead of crop()
        video_clip = video_clip.cropped(x1=x_center - new_w/2, x2=x_center + new_w/2, y1=0, y2=h)
    else:
        # Too tall (unlikely), crop height
        new_h = int(w / target_ratio)
        y_center = h / 2
        video_clip = video_clip.cropped(x1=0, x2=w, y1=y_center - new_h/2, y2=y_center + new_h/2)
        
    # Resize to 1080x1920
    # MoviePy 2.0: resized() instead of resize()
    video_clip = video_clip.resized(height=1920) 
    
    # Mix audio: Voiceover + Background (Original Audio lowered)
    # MoviePy 2.0: with_volume_scaled()
    if video_clip.audio:
         video_audio = video_clip.audio.with_volume_scaled(0.1) # Lower background volume to 10%
         final_audio = CompositeAudioClip([video_audio, audio_clip])
    else:
         final_audio = audio_clip # Use voiceover only if video has no audio (e.g. slideshow)
         
    video_clip = video_clip.with_audio(final_audio)

    # Add Subtitles
    text_clips = []
    
    # Use downloaded font if available, otherwise fallback
    font_name = font_path if font_path and os.path.exists(font_path) else 'Arial'
    if not font_path or not os.path.exists(font_path):
        if os.name != 'nt':
             font_name = 'DejaVu-Sans'

    logger.info(f"Using font: {font_name}")

    for word_info in words:
        word_text = process_arabic_text(word_info['word'])
        start = word_info['start']
        end = word_info['end']
        duration_txt = end - start
        
        if duration_txt <= 0: continue

        # Create TextClip
        # MoviePy 2.0: TextClip params changed. 
        # font, text, font_size, color, stroke_color, stroke_width, method, size
        # set_position -> with_position, set_start -> with_start, set_duration -> with_duration
        try:
            txt_clip = (TextClip(text=word_text, font_size=90, color='yellow', font=font_name, 
                                stroke_color='black', stroke_width=3, size=(1000, None), method='caption')
                        .with_position(('center', 1400))
                        .with_start(start)
                        .with_duration(duration_txt))
            text_clips.append(txt_clip)
        except Exception as e:
            logger.warning(f"Could not create text clip for word '{word_text}': {e}")

    # Combine
    if text_clips:
        final_video = CompositeVideoClip([video_clip] + text_clips)
    else:
        final_video = video_clip
        
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', threads=4)
    logger.info(f"Video saved to {output_path}")

# 7. Post to Facebook
def post_to_facebook(video_path, caption):
    logger.info("Uploading to Facebook...")
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        logger.warning("Facebook credentials not found. Skipping upload.")
        return

    url = f"https://graph-video.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    # Check file size
    file_size = os.path.getsize(video_path)
    logger.info(f"Video size: {file_size / (1024*1024):.2f} MB")
    
    params = {
        'access_token': FB_PAGE_TOKEN,
        'description': caption,
        'title': caption[:50]
    }
    
    # 'source' is usually the key for video file in Graph API
    files = {
        'source': open(video_path, 'rb')
    }
    
    try:
        response = requests.post(url, params=params, files=files)
        response.raise_for_status()
        logger.info(f"Video uploaded successfully: {response.json().get('id')}")
    except Exception as e:
        logger.error(f"Failed to upload video: {e}")
        if 'response' in locals():
             logger.error(f"Response: {response.text}")
             try:
                 error_data = response.json()
                 if error_data.get('error', {}).get('code') == 100:
                     logger.error("❌ PERMISSION ERROR #100: Missing Permissions!")
                     logger.error("Please enable 'pages_manage_posts' and 'pages_read_engagement' in Meta Developers Console.")
                     logger.error("🔗 Link: https://developers.facebook.com/apps/")
             except:
                 pass
    finally:
        files['source'].close()

# Main Execution
async def main():
    try:
        # 1. Get Movie
        movie = get_trending_movie()
        title = movie['title']
        overview = movie['overview']
        
        # 2. Generate Script
        script = generate_script(title, overview)
        
        # 3. Generate Audio
        audio_path = f"{TEMP_DIR}/voiceover.mp3"
        await generate_audio(script, audio_path)
        
        # Get audio duration
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        audio_clip.close() # Close to avoid lock issues
        
        # 4. Get Timestamps
        words = get_word_timestamps(audio_path)
        
        # 5. Get Video Content (Trailer or Fallback)
        video_raw_path = get_video_content(movie, audio_duration)
        
        # 6. Create Video
        output_video_path = f"{OUTPUT_DIR}/final_reel.mp4"
        create_reel(video_raw_path, audio_path, words, output_video_path)
        
        # 7. Post to Facebook
        # Ensure we have a valid page ID
        if FB_PAGE_ID:
            post_to_facebook(output_video_path, f"{title} 🔥\n\n{script[:200]}...\n\n#Cinema #Reels #Movie")
        else:
            logger.warning("FB_PAGE_ID not set, skipping upload.")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        # We don't raise here to avoid failing the Action completely if just one part fails, 
        # but for production it's better to fail so we get notified.
        raise

if __name__ == "__main__":
    asyncio.run(main())
