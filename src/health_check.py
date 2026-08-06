import json
import os
from datetime import datetime

HEALTH_LOG_FILE = ".mp/health_check.log"


def write_health_check(video_path: str, youtube: bool, tiktok: bool, facebook_profile: bool):
    os.makedirs(".mp", exist_ok=True)

    data = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "video_path": video_path,
        "youtube": youtube,
        "tiktok": tiktok,
        "facebook_profile": facebook_profile,
    }

    with open(HEALTH_LOG_FILE, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

