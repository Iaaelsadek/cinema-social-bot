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
    Act as a viral content creator. Write a short, engaging Reels script (under 60 seconds spoken) in Egyptian Arabic slang (Ammiya) for the movie "{movie_title}".
    Movie Overview: {movie_overview}
    
    Structure:
    1. Hook: A catchy opening sentence to grab attention immediately.
    2. Body: Briefly explain the plot in an exciting way without major spoilers.
    3. Call to Action: End with "تابعوا المزيد على cinma.online" (Make sure this exact phrase is included).
    
    Return ONLY the raw script text to be spoken, no headers, no scene directions. Do not include asterisks or markdown formatting.
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

# 3. Generate Audio with Edge-TTS
async def generate_audio(text, output_file):
    logger.info("Generating audio with Edge-TTS...")
    voice = "ar-EG-SalmaNeural" 
    communicate = edge_tts.Communicate(text, voice)
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

    # Tier 2: Third-Party API Fallback (Cobalt / Direct MP4)
    try:
        logger.info("[Tier 2] Attempting Third-Party API Fallback (Cobalt)...")
        # First, we need a video URL. Try to get it from yt-dlp without downloading
        ydl_opts_url = {
            'quiet': True, 
            'default_search': 'ytsearch1:', 
            'extract_flat': True # Don't download, just get info
        }
        video_url = None
        with yt_dlp.YoutubeDL(ydl_opts_url) as ydl:
            info = ydl.extract_info(f"{movie_title} official trailer", download=False)
            if 'entries' in info and info['entries']:
                 video_url = info['entries'][0]['url']
        
        if video_url:
            logger.info(f"Found Video URL: {video_url}")
            # Use Cobalt API
            cobalt_payload = {
                "url": video_url,
                "vCodec": "h264",
                "vQuality": "720",
                "aFormat": "mp3",
                "filenamePattern": "basic"
            }
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            # Note: Cobalt instances vary. Using api.cobalt.tools as requested.
            response = requests.post("https://api.cobalt.tools/api/json", json=cobalt_payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if 'url' in data:
                    direct_url = data['url']
                    logger.info("Got direct download URL from Cobalt.")
                    # Download the file
                    video_filename = f"{TEMP_DIR}/cobalt_video.mp4"
                    with requests.get(direct_url, stream=True) as r:
                        r.raise_for_status()
                        with open(video_filename, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    logger.info("[Tier 2] Success: Video downloaded via Cobalt.")
                    return video_filename
                else:
                    logger.warning(f"Cobalt response did not contain URL: {data}")
            else:
                 logger.warning(f"Cobalt API failed with status {response.status_code}")
        else:
            logger.warning("Could not find video URL for Tier 2.")
            
    except Exception as e:
        logger.warning(f"[Tier 2] Failed: {e}")

    # Tier 3: The Ultimate Slideshow Fallback (TMDB Backdrops)
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
            
        # Create Slideshow
        logger.info(f"Creating slideshow from {len(image_paths)} images...")
        clips = []
        duration_per_slide = audio_duration / len(image_paths)
        
        for img_path in image_paths:
            # Create ImageClip
            # Resize and Crop to 9:16
            clip = ImageClip(img_path).with_duration(duration_per_slide)
            
            # Smart Crop (Center) to 9:16
            w, h = clip.size
            target_ratio = 9/16
            
            # Resize to cover 1080x1920
            # If image is wider than target
            if w/h > target_ratio:
                # Resize by height
                clip = clip.resized(height=1920)
                # Crop width
                w_new = clip.size[0]
                x_center = w_new / 2
                clip = clip.cropped(x1=x_center - (1080/2), x2=x_center + (1080/2), y1=0, y2=1920)
            else:
                # Resize by width
                clip = clip.resized(width=1080)
                # Crop height
                h_new = clip.size[1]
                y_center = h_new / 2
                clip = clip.cropped(x1=0, x2=1080, y1=y_center - (1920/2), y2=y_center + (1920/2))
                
            clips.append(clip)
            
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

# 6. Create Video with MoviePy
def create_reel(video_path, audio_path, words, output_path):
    logger.info("Editing video...")
    
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
    
    # Try to find a font that supports Arabic
    # On Ubuntu, DejaVuSans is common. 
    font_name = 'DejaVu-Sans' 
    # If on Windows for local testing, might need 'Arial' or specific path
    if os.name == 'nt':
        font_name = 'Arial'

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
