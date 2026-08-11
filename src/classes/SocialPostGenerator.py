import hashlib
import json
import os
import random
import re
from datetime import datetime
from pathlib import Path

from config import ROOT_DIR, get_youtube_brand_topics_config
from llm_provider import generate_text
from status import warning
from .SocialPostImageGenerator import SocialPostImageGenerator


class SocialPostGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.output_root = Path(ROOT_DIR) / str(
            config.get("output_root", "output/social_posts")
        )

    def generate(self) -> dict:
        topic = self._select_topic()
        text = self._generate_text(topic)
        image_path = self._select_image_path()
        if not image_path:
            image_path = SocialPostImageGenerator(self.config).generate(topic, text)
        draft = {
            "id": self._draft_id(text, image_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "topic": topic,
            "text": text,
            "image_path": image_path,
            "platforms": {
                "facebook": {"enabled": self._platform_enabled("facebook")},
                "youtube": {"enabled": self._platform_enabled("youtube")},
            },
        }
        draft["draft_path"] = self.save_draft(draft)
        return draft

    def save_draft(self, draft: dict) -> str:
        self.output_root.mkdir(parents=True, exist_ok=True)
        draft_path = self.output_root / f"{draft['id']}.json"
        with draft_path.open("w", encoding="utf-8") as file:
            json.dump(draft, file, ensure_ascii=False, indent=2)
        return str(draft_path)

    def _select_topic(self) -> str:
        topics = self.config.get("topics") or []
        if topics:
            return random.choice(topics)

        brand_config = get_youtube_brand_topics_config()
        concepts = brand_config.get("concepts") or []
        keywords = brand_config.get("keywords") or []
        candidates = [str(item).strip() for item in concepts + keywords if str(item).strip()]
        if candidates:
            return random.choice(candidates)

        return str(self.config.get("brand_name", "HIEMEE"))

    def _generate_text(self, topic: str) -> str:
        language = str(self.config.get("language", "vi")).strip() or "vi"
        brand_name = str(self.config.get("brand_name", "HIEMEE")).strip() or "HIEMEE"
        tone = str(self.config.get("tone", "concise, useful")).strip()
        max_chars = int(self.config.get("max_chars", 900))
        prompt = (
            f"Write one social media post in {language} for {brand_name}.\n"
            f"Topic: {topic}\n"
            f"Tone: {tone}\n"
            "Rules:\n"
            "- If the language is Vietnamese, write only Vietnamese with common English brand/product names.\n"
            "- 2 to 5 short paragraphs.\n"
            "- No markdown headings.\n"
            "- No fake metrics, guarantees, or unsupported claims.\n"
            "- Avoid clickbait.\n"
            "- Do not write hashtags. A fixed footer will be appended separately.\n"
            "- Do not write a footer, contact block, links, or social channel list.\n"
            f"- Maximum {max_chars} characters.\n"
            "- Write only the main post body."
        )
        try:
            text = generate_text(prompt).strip()
        except Exception as exc:
            warning(f"Could not generate social post with LLM; using fallback: {exc}")
            text = (
                f"{brand_name} đang xây dựng hệ sinh thái kinh doanh xoay quanh "
                f"{topic}. Mục tiêu là biến vận hành thực tế thành dữ liệu, "
                "phần mềm và tài sản dài hạn.\n\n"
                "#HIEMEE #BusinessAutomation #FounderJourney"
            )

        body = self._clean_text(text, max_chars)
        return self._append_footer(body)

    def _clean_text(self, text: str, max_chars: int) -> str:
        cleaned = str(text).replace("```", "").strip().strip('"')
        cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()
        cleaned = self._strip_generated_footer_lines(cleaned)
        cleaned = self._strip_disallowed_scripts(cleaned)
        cleaned = self._strip_body_hashtags(cleaned)
        if len(cleaned) <= max_chars:
            return cleaned

        truncated = cleaned[: max_chars - 3].rsplit(" ", 1)[0].strip()
        return f"{truncated}..."

    def _strip_generated_footer_lines(self, text: str) -> str:
        blocked_prefixes = (
            "footer:",
            "liên hệ:",
            "contact:",
            "website:",
            "facebook:",
            "tiktok:",
            "youtube:",
            "email:",
        )
        lines = []
        for line in str(text).splitlines():
            normalized = line.strip().lower()
            if any(normalized.startswith(prefix) for prefix in blocked_prefixes):
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    def _strip_disallowed_scripts(self, text: str) -> str:
        # Strip unexpected Thai/Lao/Khmer/Myanmar script fragments that local LLMs
        # sometimes mix into Vietnamese words.
        cleaned = re.sub(r"[\u0E00-\u0E7F\u0E80-\u0EFF\u1780-\u17FF\u1000-\u109F]+", "", text)
        return cleaned

    def _strip_body_hashtags(self, text: str) -> str:
        lines = []
        for line in str(text).splitlines():
            cleaned_line = re.sub(r"(?<!\w)#\w+", "", line).rstrip()
            if cleaned_line.strip():
                lines.append(cleaned_line)
            elif lines and lines[-1] != "":
                lines.append("")

        return "\n".join(lines).strip()

    def _append_footer(self, text: str) -> str:
        footer = str(self.config.get("post_footer", "")).strip()
        if not footer:
            return text

        cleaned_text = str(text).strip()
        if footer in cleaned_text:
            return cleaned_text
        if not cleaned_text:
            return footer

        return f"{cleaned_text}\n\n{footer}"

    def _select_image_path(self) -> str:
        image_paths = self.config.get("image_paths") or []
        for raw_path in image_paths:
            path = Path(str(raw_path).strip()).expanduser()
            if not path.is_absolute():
                path = Path(ROOT_DIR) / path
            if path.exists() and path.is_file():
                return str(path)
        return ""

    def _platform_enabled(self, platform: str) -> bool:
        platforms = self.config.get("platforms", {})
        platform_config = platforms.get(platform, {})
        return bool(platform_config.get("enabled", False))

    def _draft_id(self, text: str, image_path: str) -> str:
        digest = hashlib.sha256(f"{text}\n{image_path}".encode("utf-8")).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{digest[:10]}"
