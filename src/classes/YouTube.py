import re
import base64
import json
import time
import os
import requests
import assemblyai as aai
import subprocess

from utils import *
from cache import *
from .Tts import TTS
from .Luma import Luma
from .Runway import Runway
from llm_provider import generate_text
from config import *
from status import *
from trends import get_youtube_topic_seed
from uuid import uuid4
from constants import *
from typing import List
from moviepy.editor import *
from termcolor import colored
from selenium import webdriver
from moviepy.video.fx.all import crop
from moviepy.config import change_settings
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from moviepy.video.tools.subtitles import SubtitlesClip
from webdriver_manager.firefox import GeckoDriverManager
from datetime import datetime

# Set ImageMagick Path
change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})

YOUTUBE_TITLE_MAX_LENGTH = 80
YOUTUBE_METADATA_MAX_ATTEMPTS = 4
YOUTUBE_DUPLICATE_SIMILARITY_THRESHOLD = 0.86
YOUTUBE_IMAGE_PROMPT_MAX_ATTEMPTS = 4

HIE_SOFTWARE_SEO_CONTEXT = """
Hie-Software main message:
- Website, App và Phần mềm theo yêu cầu cho doanh nghiệp.
- Thiết kế, phát triển và nâng cấp website doanh nghiệp, website bán hàng, website đa ngôn ngữ.
- Phát triển mobile app iOS/Android, backend, UI/UX và hệ thống quản trị.
- Xây dựng phần mềm quản lý, web app, dashboard, hệ thống nội bộ, tự động hóa quy trình.
- Tích hợp API, dữ liệu tập trung, nền tảng real-time, sports data, live dashboard và digital entertainment platform.
- Giá trị cốt lõi: phân tích nhu cầu, thiết kế UI/UX, phát triển, triển khai, bảo trì, hiệu suất, bảo mật, dễ mở rộng.
- CTA: Tìm hiểu thêm tại https://www.hiemee.com/hie-software hoặc Hiemee.com.
SEO keyword families:
thiết kế website theo yêu cầu, nâng cấp website doanh nghiệp, website tối ưu SEO và tốc độ,
phát triển app theo yêu cầu, app iOS Android, phần mềm quản lý theo yêu cầu,
phần mềm doanh nghiệp, web app dashboard, tự động hóa quy trình, tích hợp API,
nền tảng dữ liệu thời gian thực, sports data, digital entertainment, backend hiệu năng cao.
""".strip()

GENERIC_YOUTUBE_TITLE_PATTERNS = [
    r"^youtube shorts?$",
    r"^video (hay|mới|ngắn|viral|shorts?)$",
    r"^shorts? (hay|mới|viral)?$",
    r"^nội dung (hay|mới|hấp dẫn)$",
    r"^câu chuyện (hay|thú vị|hấp dẫn)$",
    r"^điều này sẽ khiến bạn bất ngờ$",
    r"^bạn sẽ không tin điều này$",
    r"^khoảnh khắc (bất ngờ|hài hước|đáng xem)$",
    r"^một video (hay|hài hước|thú vị|đáng xem)$",
    r"^here is (the )?title",
    r"^this video is about",
    r"^an interesting video",
    r"^a viral short",
]


def clean_youtube_metadata_text(value: object) -> str:
    text = str(value or "").replace("```json", "").replace("```", "").strip()
    text = re.sub(r"^[#*\-\s]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" “”\"'`*_[]{}()")


def trim_youtube_title(title: object, max_length: int = YOUTUBE_TITLE_MAX_LENGTH) -> str:
    cleaned = clean_youtube_metadata_text(title)
    if len(cleaned) <= max_length:
        return cleaned.rstrip(" -|,.;:")

    trimmed = cleaned[:max_length].rsplit(" ", 1)[0].strip()
    if len(trimmed) < 18:
        trimmed = cleaned[:max_length].strip()
    return trimmed.rstrip(" -|,.;:")


def youtube_title_candidates(value: object) -> list[str]:
    raw = str(value or "").replace("```json", "").replace("```", "").strip()
    if not raw:
        return []

    candidates = []
    quote_patterns = [
        r'"([^"\n]{18,140})"',
        r"“([^”\n]{18,140})”",
        r"'([^'\n]{18,140})'",
    ]

    for line in raw.splitlines() or [raw]:
        line = clean_youtube_metadata_text(line)
        if not line:
            continue

        for pattern in quote_patterns:
            candidates.extend(re.findall(pattern, line))

        if ":" in line and re.search(r"(tiêu đề|title|seo)", line, flags=re.I):
            candidates.append(line.split(":", 1)[1])

        line = re.split(
            r"\s+(?:Tương tự,|This title|Tiêu đề này|It meets|Requirements?:)",
            line,
            maxsplit=1,
            flags=re.I,
        )[0]
        line = re.split(r"\s+\((?:This title|Tiêu đề này)", line, maxsplit=1, flags=re.I)[0]
        candidates.append(line)

    deduped = []
    seen = set()
    for candidate in candidates:
        cleaned = trim_youtube_title(candidate)
        key = normalize_youtube_duplicate_text(cleaned)
        if cleaned and key and key not in seen:
            deduped.append(cleaned)
            seen.add(key)
    return deduped


def clean_youtube_description_text(value: object) -> str:
    text = str(value or "").replace("```json", "").replace("```", "").strip()
    lines = [
        clean_youtube_metadata_text(line)
        for line in text.splitlines()
        if clean_youtube_metadata_text(line)
    ]
    return "\n\n".join(lines).strip()


def normalize_youtube_duplicate_text(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def is_generic_youtube_title(title: object) -> bool:
    normalized = normalize_youtube_duplicate_text(title)
    if not normalized:
        return True
    if len(normalized) < 18:
        return True
    if normalized.count(" ") < 2:
        return True
    return any(re.search(pattern, normalized) for pattern in GENERIC_YOUTUBE_TITLE_PATTERNS)


def youtube_text_similarity(left: object, right: object) -> float:
    left_tokens = set(normalize_youtube_duplicate_text(left).split())
    right_tokens = set(normalize_youtube_duplicate_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def parse_image_prompts_response(completion: str) -> List[str]:
    cleaned_completion = (
        str(completion)
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    if "image_prompts" in cleaned_completion:
        parsed = json.loads(cleaned_completion)["image_prompts"]
    else:
        try:
            parsed = json.loads(cleaned_completion)
        except Exception:
            match = re.search(r"\[.*\]", cleaned_completion, flags=re.S)
            if not match:
                return []
            parsed = json.loads(match.group(0))

    if not isinstance(parsed, list):
        return []

    return [str(prompt).strip() for prompt in parsed if str(prompt).strip()]


def fallback_image_prompts(subject: object, script: object, count: int) -> List[str]:
    subject_text = clean_youtube_metadata_text(subject)
    script_text = clean_youtube_metadata_text(script)
    base_topic = subject_text or script_text or "business technology"
    base_topic = base_topic[:120].rstrip(" -|,.;:")

    templates = [
        "Professional business owners reviewing customer data dashboards about {topic}",
        "Modern software dashboard visualization showing growth insights for {topic}",
        "Team analyzing customer behavior and business operations related to {topic}",
        "Clean mobile app and web platform interface for {topic}",
        "Business workflow automation scene with analytics screens for {topic}",
        "Customer experience improvement concept with data charts for {topic}",
        "Digital transformation meeting focused on practical results from {topic}",
        "Hospitality and service business using technology insights for {topic}",
    ]

    prompts = [template.format(topic=base_topic) for template in templates]
    return prompts[: max(1, min(count, len(prompts)))]


class YouTube:
    """
    Class for YouTube Automation.

    Steps to create a YouTube Short:
    1. Generate a topic [DONE]
    2. Generate a script [DONE]
    3. Generate metadata (Title, Description, Tags) [DONE]
    4. Generate AI Image Prompts [DONE]
    4. Generate Images based on generated Prompts [DONE]
    5. Convert Text-to-Speech [DONE]
    6. Show images each for n seconds, n: Duration of TTS / Amount of images [DONE]
    7. Combine Concatenated Images with the Text-to-Speech [DONE]
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the firefox profile that is logged into the specificed YouTube Account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        english_mode = get_youtube_english_mode_config()
        self._language: str = english_mode["language"] if english_mode["enabled"] else language

        self.images = []
        self.image_source_urls = []
        self.ai_hook_video_path = None

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(self._fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {self._fp_profile_path}"
            )

        self._assert_firefox_profile_available()

        self.options.profile = self._fp_profile_path

        # Set the service
        self.service: Service = Service(GeckoDriverManager().install())

        # Initialize the browser
        self.browser: webdriver.Firefox = webdriver.Firefox(
            service=self.service, options=self.options
        )

    def _assert_firefox_profile_available(self) -> None:
        lock_path = os.path.join(self._fp_profile_path, ".parentlock")
        if not os.path.exists(lock_path):
            return

        active_process = self._find_firefox_process_using_profile()
        if not active_process:
            warning(
                f"Found stale Firefox profile lock, but no active Firefox process: {lock_path}"
            )
            return

        raise RuntimeError(
            "Firefox profile is currently in use. Close all Firefox windows that use "
            f"this profile before running cron: {self._fp_profile_path}. "
            "You can run `pkill -f Firefox` if no upload session is active."
        )

    def _find_firefox_process_using_profile(self) -> str:
        try:
            result = subprocess.run(
                ["pgrep", "-fl", self._fp_profile_path],
                check=False,
                capture_output=True,
                text=True,
            )
            output = result.stdout.strip()
            if not output:
                return ""

            process_lines = [
                line
                for line in output.splitlines()
                if any(name in line.lower() for name in ["firefox", "plugin-container", "geckodriver"])
            ]
            return "\n".join(process_lines)
        except Exception:
            return ""

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche

    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_response(self, prompt: str, model_name: str = None) -> str:
        """
        Generates an LLM Response based on a prompt and the user-provided model.

        Args:
            prompt (str): The prompt to use in the text generation.

        Returns:
            response (str): The generated AI Repsonse.
        """
        return generate_text(prompt, model_name=model_name)

    def generate_topic(self) -> str:
        """
        Generates a topic based on a trend keyword or the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        topic_seed = get_youtube_topic_seed(self.niche)
        info(f" => Topic seed for AI idea: {topic_seed}")
        brand_topics_config = get_youtube_brand_topics_config()
        if brand_topics_config["enabled"]:
            prompt = (
                "Please generate one specific, brand-safe YouTube Shorts idea "
                "for the HIEMEE ecosystem. Focus on practical business value "
                "around hospitality, software, customer data, real estate, "
                "fintech, EV technology, or the founder journey. Avoid spammy "
                "claims, sensitive news, celebrity gossip, politics, gambling, "
                "adult topics, and unrelated trends. Base the idea on this "
                f"topic seed: {topic_seed}. Make it exactly one sentence. "
                f"Write it in {self.language}. Only return the topic, nothing else."
            )
        else:
            prompt = (
                "Please generate a specific video idea that talks about the "
                f"following topic: {topic_seed}. Make it exactly one sentence. "
                f"Write it in {self.language}. Only return the topic, nothing else."
            )

        completion = self.generate_response(prompt)

        if not completion:
            error("Failed to generate Topic.")

        self.subject = completion
        info(f" => Generated AI video idea: {self.subject}")
        self._write_topic_seed_debug(topic_seed, self.subject)

        return completion

    def _write_topic_seed_debug(self, topic_seed: str, generated_idea: str) -> None:
        debug_path = os.path.join(ROOT_DIR, ".mp", "last_topic_seed.json")
        trends_config = get_youtube_trends_config()
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "youtube_trends": trends_config,
            "youtube_brand_topics": get_youtube_brand_topics_config(),
            "account_niche": self.niche,
            "topic_seed_used": topic_seed,
            "generated_ai_video_idea": generated_idea,
        }

        try:
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            info(f" => Wrote topic seed debug: {debug_path}")
        except Exception as exc:
            warning(f"Could not write topic seed debug file: {exc}")

    def generate_script(self) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        prompt = f"""
        Generate a script for a video in {sentence_length} sentences, depending on the subject of the video.

        The script is to be returned as a string with the specified number of paragraphs.

        Here is an example of a string:
        "This is an example string."

        Do not under any circumstance reference this prompt in your response.

        Get straight to the point, don't start with unnecessary things like, "welcome to this video".

        Obviously, the script should be related to the subject of the video.
        
        YOU MUST NOT EXCEED THE {sentence_length} SENTENCES LIMIT. MAKE SURE THE {sentence_length} SENTENCES ARE SHORT.
        YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.
        YOU MUST WRITE THE SCRIPT IN THE LANGUAGE SPECIFIED IN [LANGUAGE].
        ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS OF WHAT SHOULD BE SPOKEN AT THE BEGINNING OF EACH PARAGRAPH OR LINE. YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF. ALSO, NEVER TALK ABOUT THE AMOUNT OF PARAGRAPHS OR LINES. JUST WRITE THE SCRIPT
        
        Subject: {self.subject}
        Language: {self.language}
        """
        completion = self.generate_response(prompt)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            return

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()

        self.script = completion

        return completion

    def _youtube_title_prompt(self, attempt: int) -> str:
        uniqueness_hint = ""
        previous_titles = self._recent_video_titles(limit=8)
        if previous_titles:
            uniqueness_hint = (
                "\nAvoid these previously used titles and do not rewrite them too closely:\n"
                + "\n".join(f"- {title}" for title in previous_titles)
            )

        if self._is_english_mode_enabled():
            return f"""
        Create exactly 1 SEO-ready English YouTube Shorts title.

        Topic: {self.subject}
        Channel niche/account context: {self.niche}
        Brand/product context:
        {HIE_SOFTWARE_SEO_CONTEXT}

        Requirements:
        - Under {YOUTUBE_TITLE_MAX_LENGTH} characters
        - Specific enough to rank/search, not generic
        - Match the actual topic and spoken script
        - Use one relevant SEO keyword naturally when it fits
        - Suitable for business owners looking for websites, apps, custom software, dashboards, APIs, real-time data, sports data, or digital entertainment platforms
        - No markdown, no quotation marks, no numbering, no explanation
        - Return exactly 1 title only
        Attempt: {attempt}
        {uniqueness_hint}
        """

        return f"""
        Tạo đúng 1 tiêu đề YouTube Shorts chuẩn SEO bằng tiếng Việt.

        Chủ đề video: {self.subject}
        Ngữ cảnh kênh/tài khoản: {self.niche}
        Thông điệp thương hiệu và nhóm từ khóa:
        {HIE_SOFTWARE_SEO_CONTEXT}

        Yêu cầu:
        - Dưới {YOUTUBE_TITLE_MAX_LENGTH} ký tự
        - Cụ thể, có ý định tìm kiếm rõ ràng, không chung chung
        - Khớp với nội dung video và lời thoại
        - Ưu tiên tự nhiên các nhóm từ khóa: website theo yêu cầu, mobile app, phần mềm doanh nghiệp, dashboard, API, real-time data, sports data, digital entertainment
        - Không giật tít sai sự thật, không spam keyword
        - Không markdown, không dấu ngoặc kép, không đánh số, không giải thích
        - Chỉ trả về đúng 1 tiêu đề
        Lần thử: {attempt}
        {uniqueness_hint}
        """

    def _youtube_description_prompt(self, title: str) -> str:
        if self._is_english_mode_enabled():
            return f"""
        Write an SEO-ready YouTube Shorts description in English.

        Title: {title}
        Topic: {self.subject}
        Channel niche/account context: {self.niche}
        Spoken script:
        {self.script}

        Brand/product context:
        {HIE_SOFTWARE_SEO_CONTEXT}

        Requirements:
        - 2 short paragraphs, natural and useful
        - Must align with the title and script
        - Mention Hie-Software only when it fits the topic
        - Include a soft CTA to visit https://www.hiemee.com/hie-software or Hiemee.com
        - Add 3-6 relevant hashtags at the end
        - No markdown headings, no bullet list, no explanation
        - Return only the final description
        """

        return f"""
        Viết mô tả YouTube Shorts chuẩn SEO bằng tiếng Việt.

        Tiêu đề: {title}
        Chủ đề video: {self.subject}
        Ngữ cảnh kênh/tài khoản: {self.niche}
        Lời thoại video:
        {self.script}

        Thông điệp thương hiệu và nhóm từ khóa:
        {HIE_SOFTWARE_SEO_CONTEXT}

        Yêu cầu:
        - 2 đoạn ngắn, tự nhiên, có giá trị cho chủ doanh nghiệp
        - Phải thống nhất với tiêu đề và lời thoại
        - Nhắc Hie-Software khi phù hợp với chủ đề
        - Có CTA mềm tới https://www.hiemee.com/hie-software hoặc Hiemee.com
        - Cuối mô tả có 3-6 hashtag liên quan
        - Không tiêu đề markdown, không bullet list, không giải thích
        - Chỉ trả về phần mô tả hoàn chỉnh
        """

    def _clean_youtube_title(self, title: object) -> str:
        candidates = youtube_title_candidates(title)
        cleaned = candidates[0] if candidates else clean_youtube_metadata_text(title)
        cleaned = cleaned.splitlines()[0] if "\n" in cleaned else cleaned
        cleaned = re.sub(r"^\d+[\).\-\s]+", "", cleaned).strip()
        return trim_youtube_title(cleaned)

    def _is_good_youtube_title(self, title: str) -> bool:
        if not title:
            return False
        if len(title) > YOUTUBE_TITLE_MAX_LENGTH:
            return False
        if title.startswith(("{", "[")):
            return False
        if any(mark in title for mark in ["```", "**", "##"]):
            return False
        return not is_generic_youtube_title(title)

    def _recent_video_titles(self, limit: int = 8) -> list[str]:
        titles = []
        try:
            for video in reversed(self.get_videos()):
                title = clean_youtube_metadata_text(video.get("title", ""))
                if title:
                    titles.append(title)
                if len(titles) >= limit:
                    break
        except Exception as exc:
            warning(f"Could not read previous YouTube titles for duplicate guard: {exc}")
        return titles

    def _fallback_youtube_title(self, last_title: str = "") -> str:
        candidates = []
        candidates.extend(youtube_title_candidates(last_title))
        candidates.extend(youtube_title_candidates(getattr(self, "subject", "")))

        script = clean_youtube_metadata_text(getattr(self, "script", ""))
        if script:
            candidates.extend(youtube_title_candidates(script.split(".")[0]))

        fallback_suffix = "Hie-Software"
        for candidate in candidates:
            title = trim_youtube_title(candidate)
            if self._is_good_youtube_title(title):
                return title

            if is_generic_youtube_title(title):
                continue

            with_brand = trim_youtube_title(f"{title} cùng {fallback_suffix}")
            if self._is_good_youtube_title(with_brand):
                return with_brand

        if self._is_english_mode_enabled():
            return "Custom Software Helps Businesses Use Customer Data"
        return "Phần Mềm Doanh Nghiệp Giúp Khai Thác Dữ Liệu Khách Hàng"

    def _fallback_youtube_description(self, title: str) -> str:
        subject = clean_youtube_metadata_text(getattr(self, "subject", ""))
        script = clean_youtube_metadata_text(getattr(self, "script", ""))
        if self._is_english_mode_enabled():
            return (
                f"{title}. {subject or script}\n\n"
                "Hie-Software helps businesses build websites, apps, dashboards, "
                "APIs, and internal software that turn customer data into clearer "
                "operations. Learn more at https://www.hiemee.com/hie-software "
                "#HieSoftware #BusinessSoftware #CustomerData"
            )

        return (
            f"{title}. {subject or script}\n\n"
            "Hie-Software giúp doanh nghiệp xây dựng website, app, dashboard, API "
            "và phần mềm nội bộ để biến dữ liệu khách hàng thành lợi thế vận hành. "
            "Tìm hiểu thêm tại https://www.hiemee.com/hie-software "
            "#HieSoftware #PhanMemDoanhNghiep #DuLieuKhachHang"
        )

    def _is_duplicate_title_or_content(self, title: str, description: str = "") -> bool:
        title_norm = normalize_youtube_duplicate_text(title)
        subject_norm = normalize_youtube_duplicate_text(getattr(self, "subject", ""))
        script_norm = normalize_youtube_duplicate_text(getattr(self, "script", ""))
        description_norm = normalize_youtube_duplicate_text(description)

        for video in self.get_videos():
            existing_title = video.get("title", "")
            existing_description = video.get("description", "")
            existing_subject = video.get("subject", "")
            existing_script = video.get("script", "")

            if title_norm and title_norm == normalize_youtube_duplicate_text(existing_title):
                return True
            if youtube_text_similarity(title, existing_title) >= YOUTUBE_DUPLICATE_SIMILARITY_THRESHOLD:
                return True
            if subject_norm and subject_norm == normalize_youtube_duplicate_text(existing_subject):
                return True
            if script_norm and script_norm == normalize_youtube_duplicate_text(existing_script):
                return True
            if description_norm and description_norm == normalize_youtube_duplicate_text(existing_description):
                return True
            if script_norm and youtube_text_similarity(script_norm, existing_script) >= YOUTUBE_DUPLICATE_SIMILARITY_THRESHOLD:
                return True

        return False

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description).

        Returns:
            metadata (dict): The generated metadata.
        """
        last_title = ""
        for attempt in range(1, YOUTUBE_METADATA_MAX_ATTEMPTS + 1):
            raw_title = self.generate_response(self._youtube_title_prompt(attempt))
            title = self._clean_youtube_title(raw_title)
            last_title = title

            if not self._is_good_youtube_title(title):
                warning(f"Generated YouTube title is invalid/generic. Retrying: {title!r}")
                continue

            if self._is_duplicate_title_or_content(title):
                warning(f"Generated YouTube title/content is duplicate. Retrying: {title!r}")
                continue

            description = clean_youtube_description_text(
                self.generate_response(self._youtube_description_prompt(title))
            )

            if not description:
                warning("Generated YouTube description is empty. Retrying metadata generation.")
                continue

            if self._is_duplicate_title_or_content(title, description):
                warning(f"Generated YouTube description/content is duplicate. Retrying: {title!r}")
                continue

            self.metadata = {
                "title": title,
                "description": description[:4500],
                "subject": getattr(self, "subject", ""),
                "script": getattr(self, "script", ""),
            }

            return self.metadata

        title = self._fallback_youtube_title(last_title)
        description = self._fallback_youtube_description(title)
        warning(
            "Using fallback YouTube metadata after "
            f"{YOUTUBE_METADATA_MAX_ATTEMPTS} invalid/generic attempts. "
            f"Fallback title: {title!r}"
        )

        self.metadata = {
            "title": title,
            "description": description[:4500],
            "subject": getattr(self, "subject", ""),
            "script": getattr(self, "script", ""),
        }
        return self.metadata

    def _metadata_is_duplicate(self) -> bool:
        metadata = getattr(self, "metadata", {})
        return self._is_duplicate_title_or_content(
            metadata.get("title", ""),
            metadata.get("description", ""),
        )

    def _is_english_mode_enabled(self) -> bool:
        return get_youtube_english_mode_config()["enabled"]

    def generate_prompts(self) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        n_prompts = min(max(get_script_sentence_length() + 2, 4), 8)

        prompt = f"""
        Generate {n_prompts} Image Prompts for AI Image Generation,
        depending on the subject of a video.
        Subject: {self.subject}

        The image prompts are to be returned as
        a JSON-Array of strings.

        Each search term should consist of a full sentence,
        always add the main subject of the video.

        Be emotional and use interesting adjectives to make the
        Image Prompt as detailed as possible.

        YOU MUST ONLY RETURN THE JSON-ARRAY OF STRINGS.
        YOU MUST NOT RETURN ANYTHING ELSE.
        YOU MUST NOT RETURN THE SCRIPT.

        The search terms must be related to the subject of the video.
        Here is an example of a JSON-Array of strings:
        ["image prompt 1", "image prompt 2", "image prompt 3"]

        For context, here is the full text:
        {self.script}
        """

        image_prompts = []
        for attempt in range(1, YOUTUBE_IMAGE_PROMPT_MAX_ATTEMPTS + 1):
            completion = str(self.generate_response(prompt))
            image_prompts = parse_image_prompts_response(completion)

            if image_prompts:
                break

            if get_verbose():
                warning(
                    "Failed to generate Image Prompts. "
                    f"Retrying ({attempt}/{YOUTUBE_IMAGE_PROMPT_MAX_ATTEMPTS})..."
                )

        if len(image_prompts) == 0:
            image_prompts = fallback_image_prompts(self.subject, self.script, n_prompts)
            warning(
                "Using fallback Image Prompts after "
                f"{YOUTUBE_IMAGE_PROMPT_MAX_ATTEMPTS} failed attempts."
            )

        if get_verbose() and image_prompts:
            info(f" => Generated Image Prompts: {image_prompts}")

        if len(image_prompts) > n_prompts:
            image_prompts = image_prompts[: int(n_prompts)]

        self.image_prompts = image_prompts

        success(f"Generated {len(image_prompts)} Image Prompts.")

        return image_prompts

    def _persist_image(self, image_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated image bytes to a PNG file in .mp.

        Args:
            image_bytes (bytes): Image payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute image path
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        if get_verbose():
            info(f' => Wrote image from {provider_label} to "{image_path}"')

        self.images.append(image_path)
        return image_path

    def generate_image_nanobanana2(self, prompt: str) -> str:
        """
        Generates an AI Image using Nano Banana 2 API (Gemini image API).
        """
        print(f"Generating Image using Nano Banana 2 API: {prompt}")

        api_key = get_nanobanana2_api_key()
        if not api_key:
            error("nanobanana2_api_key is not configured.")
            return None

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        aspect_ratio = get_nanobanana2_aspect_ratio()

        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        try:
            response = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            body = response.json()

            candidates = body.get("candidates", [])
            for candidate in candidates:
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not inline_data:
                        continue

                    data = inline_data.get("data")
                    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")

                    if data and str(mime_type).startswith("image/"):
                        image_bytes = base64.b64decode(data)
                        return self._persist_image(image_bytes, "Nano Banana 2 API")

            if get_verbose():
                warning(f"Nano Banana 2 did not return an image payload. Response: {body}")

            return None

        except Exception as e:
                if get_verbose():
                    warning(f"Failed to generate image with Nano Banana 2 API: {str(e)}")
                return None

    def generate_image_pexels(self, prompt: str) -> str:
        """
        Downloads a stock photo from Pexels and stores it in .mp.
        """
        print(f"Generating Image using Pexels API: {prompt}")

        api_key = get_pexels_api_key()
        if not api_key:
            warning("pexels_api_key is not configured.")
            return None

        search_query = prompt or self.subject or "electric vehicle finance technology"

        try:
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": api_key},
                params={
                    "query": search_query,
                    "orientation": "portrait",
                    "per_page": 1,
                },
                timeout=60,
            )
            response.raise_for_status()
            body = response.json()

            photos = body.get("photos", [])
            if not photos:
                warning(f"Pexels did not return photos for query: {search_query}")
                return None

            photo_url = photos[0]["src"].get("portrait") or photos[0]["src"].get("large")
            if not photo_url:
                warning("Pexels photo response did not include a usable image URL.")
                return None

            image_response = requests.get(photo_url, timeout=60)
            image_response.raise_for_status()

            image_path = self._persist_image(image_response.content, "Pexels API")
            self.image_source_urls.append(photo_url)
            return image_path

        except Exception as e:
            warning(f"Failed to generate image with Pexels API: {str(e)}")
            return None

    def generate_image(self, prompt: str) -> str:
        """
        Downloads/generates an image for the video.
        Prefer Pexels to avoid Gemini image API rate limits.
        """
        image_path = self.generate_image_pexels(prompt)

        if image_path:
            return image_path

        return self.generate_image_nanobanana2(prompt)

    def generate_ai_hook_video(self) -> str:
        ai_video_config = get_ai_video_config()
        if not ai_video_config["enabled"]:
            info(" => AI video hook is disabled. Set ai_video.enabled=true to call Runway.")
            return None

        if ai_video_config["provider"] not in ["runway", "luma"]:
            warning(
                f"Unsupported ai_video provider '{ai_video_config['provider']}'. "
                "Skipping AI hook video."
            )
            return None

        if ai_video_config["mode"] != "hook_only":
            warning(
                f"Unsupported ai_video mode '{ai_video_config['mode']}'. "
                "Skipping AI hook video."
            )
            return None

        if len(self.image_source_urls) == 0:
            warning(
                "No public image URL found for AI hook video. "
                "Image-to-video needs a public keyframe URL."
            )
            return None

        hook_prompt = self.generate_response(
            f"""
        Create a cinematic image-to-video prompt for a 5-second vertical social media hook.
        Subject: {self.subject}
        Visual seed: {self.image_prompts[0] if self.image_prompts else self.subject}

        Requirements:
        - realistic cinematic motion
        - subtle camera movement
        - no text, no subtitles, no logos
        - energetic but professional
        - suitable for Technology, EV, Finance short-form content
        - return only the prompt
        """
        )

        if ai_video_config["provider"] == "runway":
            api_key = get_runway_api_key()
            if not api_key:
                warning("runway_api_key is not configured. Skipping AI hook video.")
                return None

            info(f" => Generating Runway AI hook video from image URL: {self.image_source_urls[0]}")
            runway = Runway(api_key)
            self.ai_hook_video_path = runway.generate_hook_video(
                prompt=hook_prompt,
                image_url=self.image_source_urls[0],
                model=ai_video_config["model"],
                duration=self._configured_ai_hook_duration_seconds(),
                ratio=ai_video_config["ratio"],
                poll_interval_seconds=ai_video_config["poll_interval_seconds"],
                timeout_seconds=ai_video_config["timeout_seconds"],
            )
        else:
            api_key = get_luma_api_key()
            if not api_key:
                warning("luma_api_key is not configured. Skipping AI hook video.")
                return None

            info(f" => Generating Luma AI hook video from image URL: {self.image_source_urls[0]}")
            luma = Luma(api_key)
            self.ai_hook_video_path = luma.generate_hook_video(
                prompt=hook_prompt,
                image_url=self.image_source_urls[0],
                model=ai_video_config["model"],
                duration=ai_video_config["duration"],
                resolution=ai_video_config["resolution"],
                aspect_ratio=ai_video_config["aspect_ratio"],
                poll_interval_seconds=ai_video_config["poll_interval_seconds"],
                timeout_seconds=ai_video_config["timeout_seconds"],
            )

        if self.ai_hook_video_path:
            success(f'Generated {ai_video_config["provider"]} AI hook video: "{self.ai_hook_video_path}"')

        return self.ai_hook_video_path

    def _configured_ai_hook_duration_seconds(self) -> int:
        duration = get_ai_video_config()["duration"]
        match = re.search(r"\d+", duration)
        if not match:
            return 5

        return max(1, int(match.group(0)))

    def _build_hook_clip(self, max_duration: float, reserved_image_duration: float = 0):
        if not self.ai_hook_video_path or not os.path.exists(self.ai_hook_video_path):
            return None

        available_duration = max_duration - reserved_image_duration
        hook_duration = min(self._configured_ai_hook_duration_seconds(), available_duration)
        if hook_duration <= 0:
            warning(
                "Skipping AI hook video because the voiceover is too short to leave "
                "enough time for image slides."
            )
            return None

        clip = VideoFileClip(self.ai_hook_video_path).without_audio()
        if clip.duration > hook_duration:
            clip = clip.subclip(0, hook_duration)
        else:
            clip = clip.set_duration(hook_duration)

        if round((clip.w / clip.h), 4) < 0.5625:
            clip = crop(
                clip,
                width=clip.w,
                height=round(clip.w / 0.5625),
                x_center=clip.w / 2,
                y_center=clip.h / 2,
            )
        else:
            clip = crop(
                clip,
                width=round(0.5625 * clip.h),
                height=clip.h,
                x_center=clip.w / 2,
                y_center=clip.h / 2,
            )

        return clip.resize((1080, 1920)).set_fps(30).fadeout(0.4)

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using KittenTTS and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r"[^\w\s.?!]", "", self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path

        if get_verbose():
            info(f' => Wrote TTS to "{path}"')

        return path

    def add_video(self, video: dict) -> None:
        """
        Adds a video to the cache.

        Args:
            video (dict): The video to add

        Returns:
            None
        """
        videos = self.get_videos()
        videos.append(video)

        cache = get_youtube_cache_path()

        with open(cache, "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self._account_uuid:
                    account["videos"].append(video)

            # Commit changes
            with open(cache, "w") as f:
                f.write(json.dumps(previous_json))

    def generate_subtitles(self, audio_path: str) -> str:
        """
        Generates subtitles for the audio using the configured STT provider.

        Args:
            audio_path (str): The path to the audio file.

        Returns:
            path (str): The path to the generated SRT File.
        """
        provider = str(get_stt_provider() or "local_whisper").lower()

        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)

        if provider == "third_party_assemblyai":
            return self.generate_subtitles_assemblyai(audio_path)

        warning(f"Unknown stt_provider '{provider}'. Falling back to local_whisper.")
        return self.generate_subtitles_local_whisper(audio_path)

    def generate_subtitles_assemblyai(self, audio_path: str) -> str:
        """
        Generates subtitles using AssemblyAI.

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        aai.settings.api_key = get_assemblyai_api_key()
        config = aai.TranscriptionConfig()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)
        subtitles = transcript.export_subtitles_srt()

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")

        with open(srt_path, "w") as file:
            file.write(subtitles)

        return srt_path

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Formats a timestamp in seconds to SRT format.

        Args:
            seconds (float): Seconds

        Returns:
            ts (str): HH:MM:SS,mmm
        """
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3600000
        minutes = (total_millis % 3600000) // 60000
        secs = (total_millis % 60000) // 1000
        millis = total_millis % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_subtitles_local_whisper(self, audio_path: str) -> str:
        """
        Generates subtitles using local Whisper (faster-whisper).

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            error(
                "Local STT selected but 'faster-whisper' is not installed. "
                "Install it or switch stt_provider to third_party_assemblyai."
            )
            raise

        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        segments, _ = model.transcribe(audio_path, vad_filter=True)

        lines = []
        for idx, segment in enumerate(segments, start=1):
            start = self._format_srt_timestamp(segment.start)
            end = self._format_srt_timestamp(segment.end)
            text = str(segment.text).strip()

            if not text:
                continue

            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        subtitles = "\n".join(lines)
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        tts_clip = AudioFileClip(self.tts_path)
        max_duration = tts_clip.duration
        if len(self.images) == 0:
            fallback_image = os.path.join(ROOT_DIR, "assets", "fallback.png")
            print(f"⚠️ No generated images found. Using fallback image: {fallback_image}")
            self.images = [fallback_image]

        # Make a generator that returns a TextClip when called with consecutive
        generator = lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=70,
            color="#FFFF00",
            stroke_color="gray",
            stroke_width=2,
            size=(900, None),
            method="caption",
        )

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        clip_index = 0
        min_image_slide_duration = 2.5
        reserved_image_duration = (
            min_image_slide_duration if max_duration > min_image_slide_duration else max_duration * 0.5
        )
        hook_clip = self._build_hook_clip(
            max_duration,
            reserved_image_duration=reserved_image_duration,
        )
        if hook_clip is not None:
            info(f" => Prepending AI hook clip ({hook_clip.duration:.1f}s).")
            clips.append(hook_clip)
            tot_dur += hook_clip.duration
            clip_index += 1

        remaining_duration = max(max_duration - tot_dur, 0.1)
        max_image_count = max(1, int(remaining_duration // min_image_slide_duration))
        selected_images = self.images[: min(len(self.images), max_image_count)]
        if len(selected_images) < len(self.images):
            warning(
                "Voiceover is too short for all generated slides. "
                f"Using {len(selected_images)} of {len(self.images)} images so slides stay readable."
            )

        req_dur = remaining_duration / len(selected_images)
        info(
            " => Render timing: "
            f"voiceover={max_duration:.1f}s, hook={tot_dur:.1f}s, "
            f"slides={len(selected_images)}, slide_duration={req_dur:.1f}s"
        )

        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        for image_path in selected_images:
            if tot_dur >= max_duration:
                break

            clip = ImageClip(image_path)
            clip_duration = min(req_dur, max_duration - tot_dur)
            clip = clip.set_duration(clip_duration)
            clip = clip.set_fps(30)

            # Not all images are same size,
            # so we need to resize them
            if round((clip.w / clip.h), 4) < 0.5625:
                if get_verbose():
                    info(f" => Resizing Image: {image_path} to 1080x1920")
                clip = crop(
                    clip,
                    width=clip.w,
                    height=round(clip.w / 0.5625),
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                )
            else:
                if get_verbose():
                    info(f" => Resizing Image: {image_path} to 1920x1080")
                clip = crop(
                    clip,
                    width=round(0.5625 * clip.h),
                    height=clip.h,
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                )
            clip = clip.resize((1080, 1920))
            # Add cinematic motion: slow zoom + subtle movement
            clip = clip.resize(lambda t: 1 + 0.04 * t)

            clip = crop(
                clip,
                width=1080,
                height=1920,
                x_center=clip.w / 2,
                y_center=clip.h / 2,
            )

            if clip_index == 0:
                # Keep frame 0 visible so social platforms do not pick a black thumbnail.
                clip = clip.fadeout(0.4)
            else:
                clip = clip.fadein(0.2).fadeout(0.4)

            clips.append(clip)
            tot_dur += clip_duration
            clip_index += 1

        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip = final_clip.set_duration(tts_clip.duration)
        final_clip = final_clip.set_fps(30)
        random_song = choose_random_song()

        subtitles = None
        try:
            subtitles_path = self.generate_subtitles(self.tts_path)
            equalize_subtitles(subtitles_path, 10)
            subtitles = SubtitlesClip(subtitles_path, generator)
            subtitles.set_pos(("center", "center"))
        except Exception as e:
            warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        random_song_clip = AudioFileClip(random_song).set_fps(44100)

        # Turn down volume
        random_song_clip = random_song_clip.fx(afx.volumex, 0.1)
        comp_audio = CompositeAudioClip([tts_clip.set_fps(44100), random_song_clip])

        final_clip = final_clip.set_audio(comp_audio)

        if subtitles is not None:
            subtitles = subtitles.set_position(("center", 1450))
            final_clip = CompositeVideoClip([final_clip, subtitles]).set_duration(
                tts_clip.duration
            )

        final_clip.write_videofile(combined_image_path, threads=threads)

        success(f'Wrote Video to "{combined_image_path}"')

        return combined_image_path

    def generate_video(self, tts_instance: TTS) -> str:
        """
        Generates a YouTube Short based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        # Generate the Topic
        self.generate_topic()

        # Generate the Script
        self.generate_script()

        # Generate the Metadata
        self.generate_metadata()

        # Generate the Image Prompts
        self.generate_prompts()

        # Generate the Images
        for prompt in self.image_prompts:
            self.generate_image(prompt)

        # Generate a short cinematic AI hook if configured.
        self.generate_ai_hook_video()

        # Generate the TTS
        self.generate_script_to_speech(tts_instance)

        # Combine everything
        path = self.combine()

        if get_verbose():
            info(f" => Generated Video: {path}")

        self.video_path = os.path.abspath(path)

        return path

    def get_channel_id(self) -> str:
        """
        Gets the Channel ID of the YouTube Account.

        Returns:
            channel_id (str): The Channel ID.
        """
        driver = self.browser
        driver.get("https://studio.youtube.com")
        time.sleep(2)
        channel_id = driver.current_url.split("/")[-1]
        self.channel_id = channel_id

        return channel_id

    def upload_video(self) -> bool:
        """
        Uploads the video to YouTube.

        Returns:
            success (bool): Whether the upload was successful or not.
        """
        try:
            if self._metadata_is_duplicate():
                warning(
                    "Refusing YouTube upload because title/content already exists "
                    "in the local YouTube cache."
                )
                self.browser.quit()
                return False

            self.get_channel_id()

            driver = self.browser
            verbose = get_verbose()

            # Go to youtube.com/upload
            driver.get("https://www.youtube.com/upload")

            # Set video file
            FILE_PICKER_TAG = "ytcp-uploads-file-picker"
            file_picker = driver.find_element(By.TAG_NAME, FILE_PICKER_TAG)
            INPUT_TAG = "input"
            file_input = file_picker.find_element(By.TAG_NAME, INPUT_TAG)
            file_input.send_keys(self.video_path)

            # Wait for upload to finish
            # Wait for upload to finish
            time.sleep(10)

            from selenium.webdriver.support.ui import WebDriverWait

            # Set title
            textboxes = WebDriverWait(driver, 60).until(
                lambda d: d.find_elements(By.ID, YOUTUBE_TEXTBOX_ID)
            )

            print(f"Found {len(textboxes)} textboxes")

            if len(textboxes) < 2:
                raise Exception(
                    f"Could not find title/description textboxes. Found {len(textboxes)}"
                )

            title_el = textboxes[0]
            description_el = textboxes[1]
            if verbose:
                info("\t=> Setting title...")

            safe_title = self.metadata["title"][:80]

            driver.execute_script(
                """
                const el = arguments[0];
                const value = arguments[1];
                el.focus();
                el.textContent = value;
                el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                title_el,
                safe_title,
            )

            if verbose:
                info("\t=> Setting description...")

            # Set description
            time.sleep(10)
            safe_description = self.metadata["description"][:4500]

            driver.execute_script(
                """
                const el = arguments[0];
                const value = arguments[1];
                el.focus();
                el.textContent = value;
                el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                description_el,
                safe_description,
            )

            time.sleep(0.5)

            # Set `made for kids` option
            if verbose:
                info("\t=> Setting `made for kids` option...")

            is_for_kids_checkbox = driver.find_element(
                By.NAME, YOUTUBE_MADE_FOR_KIDS_NAME
            )
            is_not_for_kids_checkbox = driver.find_element(
                By.NAME, YOUTUBE_NOT_MADE_FOR_KIDS_NAME
            )

            if not get_is_for_kids():
                is_not_for_kids_checkbox.click()
            else:
                is_for_kids_checkbox.click()

            time.sleep(0.5)

            # Click next
            if verbose:
                info("\t=> Clicking next...")

            next_button = driver.find_element(By.ID, YOUTUBE_NEXT_BUTTON_ID)
            next_button.click()

            # Click next again
            if verbose:
                info("\t=> Clicking next again...")
            next_button = driver.find_element(By.ID, YOUTUBE_NEXT_BUTTON_ID)
            next_button.click()

            # Wait for 2 seconds
            time.sleep(2)

            # Click next again
            if verbose:
                info("\t=> Clicking next again...")
            next_button = driver.find_element(By.ID, YOUTUBE_NEXT_BUTTON_ID)
            next_button.click()

            # Set as unlisted
            if verbose:
                info("\t=> Setting as unlisted...")

            radio_button = driver.find_elements(By.XPATH, YOUTUBE_RADIO_BUTTON_XPATH)
            radio_button[2].click()

            if verbose:
                info("\t=> Clicking done button...")

            # Click done button
            done_button = driver.find_element(By.ID, YOUTUBE_DONE_BUTTON_ID)
            done_button.click()

            # Wait for 2 seconds
            time.sleep(2)

            # Get latest video
            if verbose:
                info("\t=> Getting video URL...")

            # Get the latest uploaded video URL
            driver.get(
                f"https://studio.youtube.com/channel/{self.channel_id}/videos/short"
            )
            time.sleep(2)
            videos = driver.find_elements(By.TAG_NAME, "ytcp-video-row")
            first_video = videos[0]
            anchor_tag = first_video.find_element(By.TAG_NAME, "a")
            href = anchor_tag.get_attribute("href")
            if verbose:
                info(f"\t=> Extracting video ID from URL: {href}")

            video_id_match = re.search(r"(?:video/|watch\?v=|shorts/)([A-Za-z0-9_-]{6,})", href or "")
            if video_id_match:
                url = build_url(video_id_match.group(1))
            else:
                url = ""
                warning(" => Uploaded video, but YouTube Studio did not expose the video URL yet.")

            self.uploaded_video_url = url

            if verbose:
                if url:
                    success(f" => Uploaded Video: {url}")
                else:
                    success(" => Uploaded Video.")

            # Add video to cache
            self.add_video(
                {
                    "title": self.metadata["title"],
                    "description": self.metadata["description"],
                    "subject": self.metadata.get("subject", getattr(self, "subject", "")),
                    "script": self.metadata.get("script", getattr(self, "script", "")),
                    "url": url,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            # Close the browser
            driver.quit()

            return True
        except Exception as e:
            import traceback
            traceback.print_exc()

            print(f"UPLOAD ERROR: {e}")

            self.browser.quit()
            return False

    def get_videos(self) -> List[dict]:
        """
        Gets the uploaded videos from the YouTube Channel.

        Returns:
            videos (List[dict]): The uploaded videos.
        """
        if not os.path.exists(get_youtube_cache_path()):
            # Create the cache file
            with open(get_youtube_cache_path(), "w") as file:
                json.dump({"videos": []}, file, indent=4)
            return []

        videos = []
        # Read the cache file
        with open(get_youtube_cache_path(), "r") as file:
            previous_json = json.loads(file.read())
            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self._account_uuid:
                    videos = account["videos"]

        return videos
