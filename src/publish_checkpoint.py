import json
import os

CHECKPOINT_FILE = ".mp/publish_checkpoint.json"


def _load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return {}

    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_checkpoint(data):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)

    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_published(video_path: str, platform: str) -> bool:
    data = _load_checkpoint()
    video_key = os.path.abspath(video_path)

    return data.get(video_key, {}).get(platform) is True


def mark_published(video_path: str, platform: str):
    data = _load_checkpoint()
    video_key = os.path.abspath(video_path)

    if video_key not in data:
        data[video_key] = {}

    data[video_key][platform] = True

    _save_checkpoint(data)
