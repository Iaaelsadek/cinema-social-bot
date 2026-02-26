
import os
import sys
import logging
import asyncio
from unittest.mock import MagicMock

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("simulation_log.txt", mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Import main (which imports content_manager)
import main
import content_manager

# Setup the mock for select_best_content
def mock_select_best_content():
    logger.info("MOCK: Selecting 'Marty Supreme' for simulation...")
    
    # Try to fetch real data from Supabase if possible using main's function
    title = "Marty Supreme"
    # We can use main's function to get the watch URL
    watch_url = main.get_watch_url_from_supabase(title)
    
    # Try to get poster/trailer if possible or use defaults
    # Since we don't want to rely on scraping for this test, we use placeholders or defaults
    # But for a real "test", we should let main fetch trailer if possible.
    # We'll use a known trailer URL or let main try to find one.
    
    return {
        'Title': title,
        'Type': 'Movie',
        'Watch_URL': watch_url,
        'Poster_URL': "https://image.tmdb.org/t/p/w500/z8ZC2J42t7j8g6g2j8g6g2.jpg", # Placeholder
        'Trailer_URL': None, # Let main find it via YT search
        'overview': "A fictional biopic of the ping pong champion Marty Reisman.",
        'tmdb_id': 1084736, # TMDB ID for Marty Supreme
        'genre_ids': [18, 35], # Drama, Comedy
        'popularity_score': 500
    }

# Monkeypatch main's select_best_content
main.select_best_content = mock_select_best_content

# Monkeypatch download_viral_chunk to avoid slow yt-dlp
def mock_download_viral_chunk(duration=20):
    logger.info("MOCK: Using 'funny_banner.mp4' as viral content.")
    if os.path.exists("funny_banner.mp4"):
        return "funny_banner.mp4"
    return None

main.download_viral_chunk = mock_download_viral_chunk

# Force Simulation Mode
main.SIMULATION_MODE = True
main.ENABLE_VIDEO_GENERATION = True
main.DEBUG_SHORT_VIDEO = False 

async def run_simulation():
    logger.info("--- STARTING MARTY SUPREME SIMULATION ---")
    
    # Run the main function
    await main.main()
    
    logger.info("--- SIMULATION FINISHED ---")
    logger.info("Please check the logs above for 'Caption' and 'First Comment'.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_simulation())
