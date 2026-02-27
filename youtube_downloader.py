"""
youtube_downloader.py
حل موثّق للتحميل من YouTube في بيئة GitHub Actions.
الطريقة الوحيدة المؤكدة: iPad Safari User-Agent.
"""

import os
import subprocess
import logging
import time
import glob

log = logging.getLogger(__name__)

UA_IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

UA_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

METHODS = [
    # ✅ الطريقة الوحيدة المؤكدة النجاح
    {
        "name": "iPad-Safari-iOS17",
        "args": ["--user-agent", UA_IPAD, "-f", "18/worst[ext=mp4]/worst"],
    },
    # iPhone Safari
    {
        "name": "iPhone-Safari-iOS17",
        "args": ["--user-agent", UA_IPHONE, "-f", "18/worst[ext=mp4]/worst"],
    },
    # iPad + iOS client
    {
        "name": "iPad-UA+iOS-client",
        "args": [
            "--user-agent", UA_IPAD,
            "--extractor-args", "youtube:player_client=ios",
            "-f", "18/worst",
        ],
    },
    # iPad + رابط /watch بدل /shorts
    {
        "name": "iPad-Safari-watch-url",
        "args": ["--user-agent", UA_IPAD, "-f", "18/worst[ext=mp4]/worst"],
        "use_watch_url": True,
    },
    # cookies إن وُجدت
    {
        "name": "cookies+iPad-UA",
        "args": ["--cookies", "cookies.txt", "--user-agent", UA_IPAD, "-f", "18/worst"],
        "requires_cookies": True,
    },
    {
        "name": "cookies-only",
        "args": ["--cookies", "cookies.txt", "-f", "worst"],
        "requires_cookies": True,
    },
]


def _extract_video_id(url: str) -> str:
    import re
    patterns = [
        r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url.split("/")[-1].split("?")[0]


def _find_file(out_dir: str, prefix: str) -> str | None:
    for ext in ("mp4", "webm", "mkv", "3gp"):
        matches = glob.glob(os.path.join(out_dir, f"{prefix}*.{ext}"))
        if matches:
            # Sort by size to get the actual video if there are multiple matches
            best = max(matches, key=os.path.getsize)
            if os.path.getsize(best) > 10_000: # Min 10KB
                return best
    return None


def download_video(
    url: str,
    out_dir: str = "downloads",
    delay: float = 1.5,
) -> str | None:
    """
    حمّل فيديو YouTube مع fallback تلقائي.

    Returns: مسار الملف، أو None إذا فشل الكل.
    """
    os.makedirs(out_dir, exist_ok=True)
    vid_id = _extract_video_id(url)
    has_cookies = os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 100

    for i, method in enumerate(METHODS):
        name = method["name"]

        if method.get("requires_cookies") and not has_cookies:
            log.debug(f"[{name}] تجاوز — cookies غير موجود")
            continue

        target_url = url
        if method.get("use_watch_url"):
            target_url = f"https://www.youtube.com/watch?v={vid_id}"

        prefix = f"yt_{vid_id}_{i}"
        out_tmpl = os.path.join(out_dir, f"{prefix}.%(ext)s")

        cmd = [
            "yt-dlp",
            target_url,
            "-o", out_tmpl,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ] + method["args"]

        log.info(f"[{i+1}/{len(METHODS)}] جارٍ: {name}")

        try:
            # Using subprocess to ensure we can use all CLI flags easily
            subprocess.run(cmd, check=True, timeout=180)
            result = _find_file(out_dir, prefix)
            if result:
                size_mb = os.path.getsize(result) / 1024 / 1024
                log.info(f"✅ نجح: {name} ({size_mb:.1f} MB) → {result}")
                return result
            log.warning(f"[{name}] تم التنفيذ لكن الملف غير موجود")
        except subprocess.CalledProcessError as e:
            log.warning(f"[{name}] فشل: exit code {e.returncode}")
        except subprocess.TimeoutExpired:
            log.warning(f"[{name}] انتهت المهلة")
        except Exception as e:
            log.warning(f"[{name}] خطأ: {e}")

        time.sleep(delay)

    log.error("❌ جميع طرق التحميل فشلت")
    return None
