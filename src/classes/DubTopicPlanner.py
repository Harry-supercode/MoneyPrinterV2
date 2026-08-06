import json
import os
from datetime import datetime

from llm_provider import generate_text, get_active_model
from trends import get_trend_topic_seed


class DubTopicPlanner:
    def __init__(self, config: dict) -> None:
        self.config = config

    def select_topic(self, run_dir: str) -> dict:
        topics = self.config.get("topics", [])
        topic_mode = self.config.get("topic_mode", "trend")

        selected = ""
        reason = ""

        if topic_mode == "llm_ranked" and topics and get_active_model():
            prompt = (
                "Pick the single most viral Vietnamese dubbing search keyword from "
                f"this list and return only that keyword:\n{json.dumps(topics, ensure_ascii=False)}"
            )
            ranked = generate_text(prompt).strip()
            if ranked:
                selected = ranked
                reason = "ranked by selected LLM"
        elif topic_mode in {"config_first", "manual"} and topics:
            selected = topics[0]
            reason = "first configured topic"

        if not selected:
            fallback_topic = self.config.get("fallback_topic", "")
            selected = get_trend_topic_seed(fallback_topic).strip()
            reason = "trend keyword"

        if not selected:
            raise ValueError(
                "No dub topic selected. Enable youtube_trends in config.json or set "
                "dub_pipeline.fallback_topic / dub_pipeline.topics."
            )

        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "topic": selected,
            "keyword": selected,
            "voice": self.config.get("voice", "default"),
            "language": self.config.get("language", "vi"),
            "reason": reason,
        }

        with open(os.path.join(run_dir, "topic_selection.json"), "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        return payload
