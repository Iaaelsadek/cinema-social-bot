# Cinema Social Bot v2.0 🎬🤖

A fully automated AI-powered bot that creates and posts viral movie reels to Facebook.

## 🌟 Version 2.0 Highlights
- **Improved Storytelling**: Scripts are now between 230-250 words for deeper engagement.
- **Natural Pacing**: Optimized speech speed (0.8x) and precise pausing (0.1s/0.4s) for a cinematic feel.
- **Arabic Phonetic Engine**: Enhanced diacritics enforcement for "الْمُقَدَّم" and solar/lunar letter rules.
- **Model Fallback**: Uses `gemini-2.5-pro` with fallback to `gemini-3-flash-preview`.

## 🚀 Features

### 1. **Smart Script Generation (Gemini AI)**
- **Persona**: "Master Storyteller" (Arabic Fus'ha with Tashkeel).
- **Style**: Dramatic storytelling with full diacritics for accurate TTS.
- **Model Fallback**: Tries `gemini-2.5-flash` -> `gemini-2.5-flash-lite`.

### 2. **Natural Voiceover (Edge-TTS)**
- **Voice**: `ar-SA-HamedNeural` (Saudi Male).
- **Phonetic Cleaning**: Pre-processes text to ensure natural pronunciation of numbers and English names.

### 3. **Intelligent Video Retrieval (3-Tier System)**
- **Tier 1 (Best)**: Fetches official YouTube trailer, performs **Smart Crop** (15s snippet from the middle) to convert 16:9 to 9:16 vertical format.
- **Tier 2 (Fallback)**: Searches **Pexels** for cinematic stock footage (dark, mysterious, dramatic) matching the movie's vibe.
- **Tier 3 (Last Resort)**: Creates a dynamic slideshow from **TMDB** high-res backdrops using the **Ken Burns Effect** (Alternating Zoom In/Out).

### 4. **Professional Editing (MoviePy 2.0)**
- **Vertical Format**: 1080x1920 (9:16).
- **Typography**: Uses **Cairo Bold** font (downloaded dynamically) for Arabic subtitles.
- **Audio Mixing**: Balances voiceover with background audio.

### 5. Social Media Automation
- **Facebook API**: Uploads directly to Facebook Reels using the **Reels API** (`video_reels` endpoint) to ensure visibility on mobile devices and the Reels tab.

## �️ Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables (`.env`)**:
    ```env
    TMDB_API_KEY=your_tmdb_key
    GEMINI_API_KEY=your_gemini_key
    PEXELS_API_KEY=your_pexels_key
    FB_PAGE_TOKEN=your_fb_token
    FB_PAGE_ID=your_page_id
    ```

3.  **Run**:
    ```bash
    python main.py
    ```

## 🐛 Troubleshooting & History

### Recent Fixes
- **Font Issues**: Switched to Google Fonts GitHub raw URL for `Cairo[slnt,wght].ttf` to fix 404 errors.
- **FFmpeg/Whisper**: Added bypass logic for Whisper timestamps if FFmpeg is missing locally, preventing crashes.
- **API Keys**: Updated Gemini key to resolve 403 Forbidden errors.

### Known Limitations
- **Whisper**: Currently returns dummy timestamps if FFmpeg is not fully configured in the system PATH. Subtitles will appear but might not be perfectly synced word-by-word.
- **Tier 1**: Relies on `yt-dlp`. Optimized for anti-bot measures using **Node.js** execution and **PO Token** strategies (Web player client).
