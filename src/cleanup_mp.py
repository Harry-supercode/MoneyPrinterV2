import os
import time

MP_DIR = ".mp"

KEEP_FILES = {
    "youtube.json",
    "twitter.json",
    "publish_checkpoint.json",
    "health_check.log",
}

DELETE_EXTENSIONS = {
    ".mp4",
    ".png",
    ".jpg",
    ".jpeg",
    ".wav",
    ".mp3",
    ".srt",
}


def cleanup_mp_folder(max_age_hours: int = 24):
    if not os.path.isdir(MP_DIR):
        return

    now = time.time()
    max_age_seconds = max_age_hours * 3600

    deleted = 0

    for filename in os.listdir(MP_DIR):
        if filename in KEEP_FILES:
            continue

        path = os.path.join(MP_DIR, filename)

        if not os.path.isfile(path):
            continue

        _, ext = os.path.splitext(filename)

        if ext.lower() not in DELETE_EXTENSIONS:
            continue

        age = now - os.path.getmtime(path)

        if age >= max_age_seconds:
            try:
                os.remove(path)
                deleted += 1
            except Exception:
                pass

    print(f"Cleanup .mp done. Deleted {deleted} old files.")
