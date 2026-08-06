import json
import os
import re

from llm_provider import generate_text, get_active_model
from status import warning


CHINESE_TEXT_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class DubMetadata:
    def __init__(self, config: dict) -> None:
        self.config = config

    def generate(self, topic_selection: dict, segments: list[dict], run_dir: str) -> dict:
        keyword = self._clean_text(topic_selection.get("keyword", ""))
        source_title = self._source_title(run_dir)
        transcript_summary = self._transcript_summary(segments)
        title = self._content_fallback_title(source_title, transcript_summary, keyword)
        description = self._content_description(
            title=title,
            source_title=source_title,
            transcript_summary=transcript_summary,
            keyword=keyword,
        )
        description_from_llm = False
        hashtags = []

        if get_active_model():
            prompt = self._metadata_prompt(keyword, source_title, transcript_summary)
            try:
                parsed = json.loads(generate_text(prompt).replace("```json", "").replace("```", "").strip())
                candidate_title = self._clean_text(parsed.get("title", ""))
                if self._is_good_title(candidate_title):
                    title = candidate_title
                candidate_description = str(parsed.get("description", "")).strip()
                if candidate_description and not self._contains_chinese(candidate_description):
                    description = candidate_description
                    description_from_llm = True
                if isinstance(parsed.get("hashtags"), list):
                    candidate_hashtags = [
                        self._normalize_hashtag(tag)
                        for tag in parsed["hashtags"]
                        if self._normalize_hashtag(tag)
                    ]
                    if candidate_hashtags:
                        hashtags = self._filter_content_hashtags(candidate_hashtags)[:6]
            except Exception as exc:
                warning(f"Dub metadata JSON generation failed: {exc}")

            if not self._is_good_title(title) or self._is_generic_title(title):
                candidate_title = self._title_from_llm(
                    language=self._language_name(),
                    source_title=source_title,
                    transcript_summary=transcript_summary,
                    keyword=keyword,
                )
                if self._is_good_title(candidate_title):
                    title = candidate_title

        title = self._clean_text(title)
        if not self._is_good_title(title) or self._is_generic_title(title):
            title = self._content_fallback_title(source_title, transcript_summary, keyword)

        if not self._is_good_title(title) or self._is_generic_title(title):
            raise RuntimeError(
                "Could not create a specific dub title from source metadata, transcript, or keyword"
            )
        if not description_from_llm:
            description = self._content_description(
                title=title,
                source_title=source_title,
                transcript_summary=transcript_summary,
                keyword=keyword,
            )
        if not hashtags:
            hashtags = self._content_hashtags(title, description, keyword)

        title = self._clean_text(title)
        description = self._clean_public_metadata_text(description)
        if self._contains_chinese(title) or self._contains_chinese(description):
            description = self._content_description(
                title=title,
                source_title="",
                transcript_summary=transcript_summary,
                keyword="" if self._contains_chinese(keyword) else keyword,
            )
            description = self._clean_public_metadata_text(description)
        if self._contains_chinese(title) or self._contains_chinese(description):
            raise RuntimeError("Refusing dub metadata with Chinese text in title or description")

        metadata = {
            "title": title[:100],
            "description": description,
            "hashtags": hashtags,
            "source_reference": "source_metadata.json",
            "language": self.config.get("language", "vi"),
            "topic": topic_selection.get("topic", keyword),
            "keyword": keyword,
            "source_title": source_title,
        }

        with open(os.path.join(run_dir, "youtube_metadata.json"), "w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)

        caption = self._caption(metadata)
        with open(os.path.join(run_dir, "caption.txt"), "w", encoding="utf-8") as file:
            file.write(caption)

        with open(os.path.join(run_dir, "thumbnail_prompts.txt"), "w", encoding="utf-8") as file:
            file.write(f"{self._language_name()} short thumbnail based on: {keyword or title}\n")

        return metadata

    def _caption(self, metadata: dict) -> str:
        title = str(metadata.get("title", "")).strip()
        description = self._short_caption_description(metadata)
        hashtags = " ".join(metadata.get("hashtags", []))
        if description:
            return f"{title}\n\n{description}\n\n{hashtags}".strip()
        return f"{title}\n\n{hashtags}".strip()

    def _source_title(self, run_dir: str) -> str:
        metadata_path = os.path.join(run_dir, "source_metadata.json")
        if not os.path.exists(metadata_path):
            return ""

        try:
            with open(metadata_path, "r", encoding="utf-8") as file:
                metadata = json.load(file)
        except Exception:
            return ""

        raw_title = metadata.get("source_title", "")
        return self._clean_source_title(raw_title)

    @staticmethod
    def _clean_source_title(raw_title: object) -> str:
        lines = [
            line.strip(" “”\"'")
            for line in str(raw_title).splitlines()
            if line.strip(" “”\"'")
        ]
        filtered = []
        for line in lines:
            if re.fullmatch(r"[\d,.]+[KkMm万亿+]?", line):
                continue
            if re.search(r"\d+(?:\.\d+)?\s*(?:K|M|万|亿)\+?$", line):
                line = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:K|M|万|亿)\+?$", "", line).strip()
            if line:
                filtered.append(line)

        return DubMetadata._clean_text(" ".join(filtered[:2]))

    @staticmethod
    def _clean_text(value: object) -> str:
        text = str(value or "").replace("\n", " ").strip()
        text = re.sub(r"\s+", " ", text)
        text = text.strip(" -|,.;:[]{}()")
        return text

    def _fallback_title(self, seed: str) -> str:
        cleaned_seed = self._clean_text(seed)
        if self._is_english():
            if re.search(r"[\u4e00-\u9fff]", cleaned_seed):
                return self._title_from_chinese_keywords(cleaned_seed, language="en")
            if self._is_good_title(cleaned_seed):
                return self._truncate_title_seed(cleaned_seed)
            return ""

        if re.search(r"[\u4e00-\u9fff]", cleaned_seed):
            heuristic_title = DubMetadata._title_from_chinese_keywords(cleaned_seed)
            if heuristic_title:
                return heuristic_title
            return ""

        if DubMetadata._is_good_title(cleaned_seed):
            return self._truncate_title_seed(cleaned_seed)

        if cleaned_seed:
            return self._truncate_title_seed(cleaned_seed, max_length=100)

        return ""

    @staticmethod
    def _truncate_title_seed(seed: str, max_length: int = 82) -> str:
        if len(seed) <= max_length:
            return seed
        shortened = seed[: max_length + 1].rsplit(" ", 1)[0].rstrip(" -|,.;:")
        return shortened or seed[:max_length].rstrip(" -|,.;:")

    def _content_fallback_title(
        self,
        source_title: str,
        transcript_summary: str,
        keyword: str,
    ) -> str:
        for candidate in (source_title, transcript_summary, keyword):
            title = self._fallback_title(candidate)
            if self._is_good_title(title) and not self._is_generic_title(title):
                return title
        return ""

    def _content_description(
        self,
        title: str,
        source_title: str = "",
        transcript_summary: str = "",
        keyword: str = "",
    ) -> str:
        topic_candidates = [source_title, title, keyword]
        topic = next(
            (
                self._clean_text(candidate)
                for candidate in topic_candidates
                if self._clean_text(candidate)
                and not self._contains_chinese(self._clean_text(candidate))
            ),
            "",
        )
        context = self._clean_text(transcript_summary)
        if self._contains_chinese(context):
            context = ""
        if context and context.lower() != topic.lower():
            context = context[:220]

        if self._is_english():
            lines = [title]
            if context:
                lines.append(context)
            elif topic:
                lines.append(topic)
            return "\n\n".join(line for line in lines if line)

        lines = [title]
        if context:
            lines.append(context)
        elif topic:
            lines.append(topic)
        return "\n\n".join(line for line in lines if line)

    def _content_hashtags(self, title: str, description: str, keyword: str) -> list[str]:
        text = self._clean_text(f"{title} {description} {keyword}").casefold()
        tags = ["#Shorts"]

        mapping = [
            (["dog", "puppy", "chó", "cún"], "#DogShorts" if self._is_english() else "#ChoCung"),
            (["cat", "kitten", "mèo"], "#CatShorts" if self._is_english() else "#MeoCung"),
            (["food", "chef", "cook", "eat", "ăn", "bếp", "món"], "#FoodShorts" if self._is_english() else "#AmThuc"),
            (["travel", "lake", "city", "trip", "du lịch", "thành phố"], "#TravelShorts" if self._is_english() else "#DuLich"),
            (["work", "job", "office", "làm việc", "công việc"], "#WorkLife" if self._is_english() else "#CongViec"),
            (["family", "kid", "baby", "gia đình", "em bé"], "#FamilyShorts" if self._is_english() else "#GiaDinh"),
            (["funny", "unexpected", "surprising", "hài", "bất ngờ"], "#FunnyShorts" if self._is_english() else "#HaiHuoc"),
            (["animal", "pet", "động vật", "thú cưng"], "#PetShorts" if self._is_english() else "#ThuCung"),
        ]
        for keywords, tag in mapping:
            if any(keyword_item in text for keyword_item in keywords):
                tags.append(tag)

        return self._filter_content_hashtags(tags)[:5]

    @staticmethod
    def _filter_content_hashtags(hashtags: list[str]) -> list[str]:
        blocked = {"#review", "#viral", "#englishdub"}
        unique = []
        for hashtag in hashtags:
            normalized = DubMetadata._normalize_hashtag(hashtag)
            if (
                not normalized
                or normalized.casefold() in blocked
                or DubMetadata._contains_chinese(normalized)
            ):
                continue
            if normalized not in unique:
                unique.append(normalized)
        return unique

    def _fallback_hashtags(self) -> list[str]:
        return self._content_hashtags("", "", "")

    def _short_caption_description(self, metadata: dict) -> str:
        title = self._clean_text(metadata.get("title", ""))
        description = str(metadata.get("description", "")).strip()
        lines = [
            self._clean_text(line)
            for line in description.splitlines()
            if self._clean_text(line)
        ]
        lines = [
            line
            for line in lines
            if line != title and "source_metadata.json" not in line.lower()
        ]
        if lines:
            return lines[0][:180]

        keyword = self._clean_text(metadata.get("keyword", ""))
        source_title = self._clean_text(metadata.get("source_title", ""))
        for candidate in (source_title, keyword):
            cleaned = self._clean_text(candidate)
            if cleaned and not self._contains_chinese(cleaned):
                return cleaned[:180]
        return ""

    def _metadata_prompt(self, keyword: str, source_title: str, transcript_summary: str) -> str:
        language_name = self._language_name()
        if self._is_english():
            title_rule = (
                "The title must be natural English, 35-85 characters, not clickbait, "
                "not random foreign keywords, and must describe the actual source video."
            )
        else:
            title_rule = (
                "The title must be natural Vietnamese, 35-85 characters, not clickbait, "
                "not random English keywords, and must describe the actual source video."
            )

        return (
            f"Create YouTube Shorts metadata in {language_name} JSON. "
            "Return only valid JSON with keys title, description, hashtags. "
            "Base the title and description on the source title and transcript, not on fixed template words. "
            "Do not use generic labels such as review, viral, English Dub, dubbed video, or translated short as the main idea. "
            "Hashtags must describe the actual content or topic and must not include #review, #viral, or #englishdub. "
            f"{title_rule} "
            f"Trend keyword: {keyword or 'unknown'}\n"
            f"Source title: {source_title or 'unknown'}\n"
            f"{language_name} transcript/context: {transcript_summary or 'unknown'}"
        )

    @staticmethod
    def _is_good_title(title: str) -> bool:
        if len(title) < 18:
            return False
        if DubMetadata._contains_chinese(title):
            return False
        if title.lower() in {"twitch", "on live", "live", "review", "viral"}:
            return False
        if title.startswith("{") or title.startswith("["):
            return False
        if title.count(" ") < 2 and not re.search(r"[\u4e00-\u9fff]", title):
            return False
        return True

    @staticmethod
    def _is_generic_title(title: str) -> bool:
        generic_titles = {
            "a viral short dubbed in english",
            "viral short dubbed in english",
            "video viral trung quốc được lồng tiếng việt",
            "video viral được lồng tiếng việt",
            "khoảnh khắc hài hước được lồng tiếng việt",
            "khoảnh khắc bất ngờ trong video này",
            "khoảnh khắc hài hước đáng xem",
            "một video hài hước đáng xem",
            "một video thú vị đáng xem",
            "câu chuyện thú vị trong video này",
            "điều này sẽ khiến bạn bất ngờ",
            "bạn sẽ không tin điều này",
            "funny moment worth watching",
            "an interesting video worth watching",
            "you will not believe this",
        }
        normalized_title = DubMetadata._clean_text(title).lower()
        if normalized_title in generic_titles:
            return True
        if normalized_title.startswith("viral short dubbed in english:"):
            return True

        generic_patterns = [
            r"^(một|mot) video (hay|hài hước|hai huoc|thú vị|thu vi|đáng xem|dang xem)",
            r"^khoảnh khắc (bất ngờ|bat ngo|hài hước|hai huoc|đáng xem|dang xem)",
            r"^câu chuyện (hay|thú vị|thu vi|hấp dẫn|hap dan)",
            r"^điều này (sẽ )?khiến bạn bất ngờ",
            r"^bạn sẽ không tin",
            r"^video (viral|hài|hai|hay|mới|moi|ngắn|ngan)",
            r"^shorts? (viral|funny|interesting|worth watching)",
            r"^a (funny|viral|interesting|surprising) (short|video|moment)",
            r"^this (short|video) (is )?(funny|interesting|surprising)",
            r"^you won'?t believe",
        ]
        return any(re.search(pattern, normalized_title) for pattern in generic_patterns)

    @staticmethod
    def _transcript_summary(segments: list[dict]) -> str:
        texts = []
        for segment in segments[:8]:
            text = str(segment.get("text_vi") or segment.get("text") or "").strip()
            if not text:
                continue
            if DubMetadata._contains_chinese(text):
                continue
            if segment.get("asr_fallback") and "xem hết video" in text.lower():
                continue
            if segment.get("asr_fallback") and "watch this video" in text.lower():
                continue
            texts.append(text)

        return DubMetadata._clean_text(" ".join(texts))[:300]

    @staticmethod
    def _title_from_llm(
        source_title: str,
        transcript_summary: str,
        keyword: str,
        language: str = "Vietnamese",
    ) -> str:
        if not get_active_model():
            return ""

        if language == "English":
            prompt = (
                "Write exactly 1 YouTube Shorts title in English for this source video. "
                "Do not use Chinese, do not add explanations. "
                "The title must be 35-85 characters, natural, and describe the real video. "
                "If the source title is Chinese, translate the meaning and rewrite it naturally.\n"
                f"Source title: {source_title or 'unknown'}\n"
                f"English transcript: {transcript_summary or 'unknown'}\n"
                f"Trend keyword: {keyword or 'unknown'}"
            )
        else:
            prompt = (
                "Viết đúng 1 tiêu đề YouTube Shorts bằng tiếng Việt cho video nguồn này. "
                "Không dùng tiếng Trung, không dùng tiếng Anh rời rạc, không thêm giải thích. "
                "Tiêu đề dài 35-85 ký tự, tự nhiên, mô tả nội dung thật của video. "
                "Nếu tiêu đề nguồn là tiếng Trung, hãy dịch ý và viết lại hấp dẫn nhưng không giật tít.\n"
                f"Tiêu đề nguồn: {source_title or 'không có'}\n"
                f"Transcript tiếng Việt: {transcript_summary or 'không có'}\n"
                f"Keyword trend: {keyword or 'không có'}"
            )

        try:
            return DubMetadata._clean_text(
                generate_text(prompt)
                .replace("```", "")
                .strip()
                .splitlines()[0]
            )
        except Exception as exc:
            warning(f"Dub title generation failed: {exc}")
            return ""

    def _is_english(self) -> bool:
        return str(self.config.get("language", "vi")).strip().lower().startswith("en")

    def _language_name(self) -> str:
        if self._is_english():
            return "English"
        return "Vietnamese"

    @staticmethod
    def _title_from_chinese_keywords(text: str, language: str = "vi") -> str:
        title_lower = text.lower()
        has_dog = any(token in text for token in ["狗", "小狗", "犬"])
        has_cat = any(token in text for token in ["猫", "猫猫"])
        has_rain = any(token in text for token in ["下雨", "雨天", "路滑"])
        has_food = any(token in text for token in ["吃", "要吃", "食"])
        has_cute = any(token in text for token in ["可爱", "萌"])
        has_aircon = "空调" in text

        if language == "en":
            if has_dog and has_rain:
                return "A Dog's Slippery Rainy-Day Adventure"
            if has_dog and has_food:
                return "A Hungry Dog's Funniest Food Request"
            if has_cat and has_cute:
                return "An Adorable Cat Steals the Show"
            if has_aircon:
                return "The Funniest Air Conditioner Moment"
            if has_dog:
                return "A Dog's Unexpectedly Funny Moment"
            if has_cat:
                return "A Cat's Unexpectedly Cute Moment"
            if "章鱼" in text or "octopus" in title_lower:
                return "An Octopus Starts a Surprising New Job"
            return ""

        if has_dog and has_rain:
            return "Chú chó trượt ngã trong ngày mưa"
        if has_dog and has_food:
            return "Chú chó xin ăn siêu hài"
        if has_cat and has_cute:
            return "Khoảnh khắc mèo cưng siêu đáng yêu"
        if has_aircon:
            return "Pha bật điều hòa hài hước"
        if has_dog:
            return "Khoảnh khắc chú chó hài hước"
        if has_cat:
            return "Khoảnh khắc mèo cưng bất ngờ"
        if "章鱼" in text or "octopus" in title_lower:
            return "Chú bạch tuộc bắt đầu công việc mới"

        return ""

    @staticmethod
    def _normalize_hashtag(value: object) -> str:
        tag = str(value or "").strip()
        if not tag:
            return ""
        tag = re.sub(r"\s+", "", tag)
        if not tag.startswith("#"):
            tag = f"#{tag}"
        return tag[:40]

    @staticmethod
    def _contains_chinese(value: object) -> bool:
        return bool(CHINESE_TEXT_RE.search(str(value or "")))

    @staticmethod
    def _clean_public_metadata_text(value: object) -> str:
        lines = [
            DubMetadata._clean_text(line)
            for line in str(value or "").splitlines()
            if DubMetadata._clean_text(line)
        ]
        clean_lines = [
            line for line in lines if not DubMetadata._contains_chinese(line)
        ]
        return "\n\n".join(clean_lines)
