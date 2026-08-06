import json
import os

from config import ROOT_DIR


CHECKPOINT_PATH = os.path.join(ROOT_DIR, ".mp", "dub_source_checkpoint.json")


def _load_checkpoint() -> dict:
    if not os.path.exists(CHECKPOINT_PATH):
        return {}

    try:
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _save_checkpoint(data: dict) -> None:
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def is_source_processed(source_url: str) -> bool:
    return bool(_load_checkpoint().get(str(source_url), {}).get("processed"))


def mark_source_processed(source_url: str, video_path: str) -> None:
    data = _load_checkpoint()
    data[str(source_url)] = {
        "processed": True,
        "video_path": os.path.abspath(video_path),
    }
    _save_checkpoint(data)

