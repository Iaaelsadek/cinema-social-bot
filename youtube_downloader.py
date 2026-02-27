import os
import logging

logger = logging.getLogger(__name__)

def download_video(url, out_dir="temp"):
    """
    MANUAL REWRITE: yt-dlp downloading is disabled.
    This function now returns None as videos must be uploaded manually via Telegram.
    """
    logger.warning(f"Automated download disabled for URL: {url}")
    logger.info("System is now in Hybrid Mode. Please upload the video via Telegram.")
    return None
