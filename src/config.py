import os
import sys
import json
import srt_equalizer

from termcolor import colored

ROOT_DIR = os.path.dirname(sys.path[0])

def assert_folder_structure() -> None:
    """
    Make sure that the nessecary folder structure is present.

    Returns:
        None
    """
    # Create the .mp folder
    if not os.path.exists(os.path.join(ROOT_DIR, ".mp")):
        if get_verbose():
            print(colored(f"=> Creating .mp folder at {os.path.join(ROOT_DIR, '.mp')}", "green"))
        os.makedirs(os.path.join(ROOT_DIR, ".mp"))

def get_first_time_running() -> bool:
    """
    Checks if the program is running for the first time by checking if .mp folder exists.

    Returns:
        exists (bool): True if the program is running for the first time, False otherwise
    """
    return not os.path.exists(os.path.join(ROOT_DIR, ".mp"))

def get_email_credentials() -> dict:
    """
    Gets the email credentials from the config file.

    Returns:
        credentials (dict): The email credentials
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["email"]

def get_verbose() -> bool:
    """
    Gets the verbose flag from the config file.

    Returns:
        verbose (bool): The verbose flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["verbose"]

def get_firefox_profile_path() -> str:
    """
    Gets the path to the Firefox profile.

    Returns:
        path (str): The path to the Firefox profile
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["firefox_profile"]

def get_firefox_binary_path() -> str:
    """
    Gets the Firefox executable path from the config file.

    Returns:
        path (str): The Firefox executable path, or empty string if not set.
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return str(json.load(file).get("firefox_binary_path", "")).strip()

def get_headless() -> bool:
    """
    Gets the headless flag from the config file.

    Returns:
        headless (bool): The headless flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["headless"]

def get_ollama_base_url() -> str:
    """
    Gets the Ollama base URL.

    Returns:
        url (str): The Ollama base URL
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("ollama_base_url", "http://127.0.0.1:11434")

def get_ollama_model() -> str:
    """
    Gets the Ollama model name from the config file.

    Returns:
        model (str): The Ollama model name, or empty string if not set.
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("ollama_model", "")

def get_twitter_language() -> str:
    """
    Gets the Twitter language from the config file.

    Returns:
        language (str): The Twitter language
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["twitter_language"]

def get_youtube_trends_config() -> dict:
    """
    Gets the YouTube trend topic configuration with safe defaults.

    Returns:
        config (dict): Sanitized trend topic configuration
    """
    defaults = {
        "enabled": False,
        "source": "google_trending_rss",
        "geo": "VN",
        "hl": "vi",
        "category_filter": "",
        "max_items": 10,
        "safety_filter_enabled": True,
        "unsafe_keywords": [
            "bet",
            "betting",
            "đánh bạc",
            "danh bac",
            "sportsbook",
            "casino",
            "gambling",
            "poker",
            "lottery",
            "cá cược",
            "ca cuoc",
            "nhà cái",
            "nha cai",
            "tài xỉu",
            "tai xiu",
            "xóc đĩa",
            "xoc dia",
            "lô đề",
            "lo de",
            "xem bóng đá",
            "xem bong da",
            "bóng đá live",
            "bong da live",
            "trực tiếp bóng đá",
            "truc tiep bong da",
            "18+",
            "sex",
            "porn",
            "onlyfans",
            "ma túy",
            "ma tuy",
            "drug",
            "vũ khí",
            "vu khi",
            "weapon",
            "scam",
            "lừa đảo",
            "lua dao",
            "hack",
            "crack",
            "piracy",
            "war",
            "terror",
            "suicide",
            "tự tử",
            "tu tu",
            "giết",
            "giet",
            "murder",
        ],
    }

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("youtube_trends", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    max_items = raw_config.get("max_items", defaults["max_items"])
    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        max_items = defaults["max_items"]

    unsafe_keywords = raw_config.get("unsafe_keywords", defaults["unsafe_keywords"])
    if not isinstance(unsafe_keywords, list):
        unsafe_keywords = defaults["unsafe_keywords"]

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "source": str(raw_config.get("source", defaults["source"])).strip(),
        "geo": str(raw_config.get("geo", defaults["geo"])).strip().upper() or defaults["geo"],
        "hl": str(raw_config.get("hl", defaults["hl"])).strip() or defaults["hl"],
        "category_filter": str(raw_config.get("category_filter", defaults["category_filter"])).strip(),
        "max_items": max(1, min(max_items, 25)),
        "safety_filter_enabled": bool(
            raw_config.get(
                "safety_filter_enabled",
                defaults["safety_filter_enabled"],
            )
        ),
        "unsafe_keywords": [
            str(keyword).strip()
            for keyword in unsafe_keywords
            if str(keyword).strip()
        ],
    }

def get_youtube_brand_topics_config() -> dict:
    """
    Gets the brand-safe YouTube Shorts topic configuration.

    Returns:
        config (dict): Sanitized brand topic configuration
    """
    defaults = {
        "enabled": False,
        "keywords": [
            "HIEMEE business ecosystem",
            "cashflow to technology to assets",
            "hospitality technology real estate",
        ],
        "concepts": [
            "HIEMEE builds a business ecosystem from restaurant cashflow, software systems, and long-term real estate assets.",
            "Hie-Palace creates real customer demand, Hie-Software turns operations into systems, and HieRealty compounds value into assets.",
        ],
    }

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("youtube_brand_topics", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    keywords = raw_config.get("keywords", defaults["keywords"])
    if not isinstance(keywords, list):
        keywords = defaults["keywords"]

    concepts = raw_config.get("concepts", defaults["concepts"])
    if not isinstance(concepts, list):
        concepts = defaults["concepts"]

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "keywords": [
            str(keyword).strip()
            for keyword in keywords
            if str(keyword).strip()
        ],
        "concepts": [
            str(concept).strip()
            for concept in concepts
            if str(concept).strip()
        ],
    }

def get_youtube_english_mode_config() -> dict:
    """
    Gets the YouTube Shorts English-mode switch.

    Returns:
        config (dict): Sanitized English-mode config.
    """
    defaults = {
        "enabled": False,
        "language": "English",
        "voice": "en-US-GuyNeural",
        "fallback_voices": ["en-US-JennyNeural"],
    }

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("youtube_english_mode", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    fallback_voices = raw_config.get("fallback_voices", defaults["fallback_voices"])
    if not isinstance(fallback_voices, list):
        fallback_voices = defaults["fallback_voices"]

    fallback_voices = [
        str(voice).strip()
        for voice in fallback_voices
        if str(voice).strip()
    ]

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "language": str(raw_config.get("language", defaults["language"])).strip()
        or defaults["language"],
        "voice": str(raw_config.get("voice", defaults["voice"])).strip()
        or defaults["voice"],
        "fallback_voices": fallback_voices or defaults["fallback_voices"],
    }

def get_nanobanana2_api_base_url() -> str:
    """
    Gets the Nano Banana 2 (Gemini image) API base URL.

    Returns:
        url (str): API base URL
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get(
            "nanobanana2_api_base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        )

def get_nanobanana2_api_key() -> str:
    """
    Gets the Nano Banana 2 API key.

    Returns:
        key (str): API key
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = json.load(file).get("nanobanana2_api_key", "")
        return configured or os.environ.get("GEMINI_API_KEY", "")

def get_pexels_api_key() -> str:
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = json.load(file).get("pexels_api_key", "")
        return configured or os.environ.get("PEXELS_API_KEY", "")

def get_luma_api_key() -> str:
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = json.load(file).get("luma_api_key", "")
        return configured or os.environ.get("LUMA_API_KEY", "")

def get_runway_api_key() -> str:
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        configured = json.load(file).get("runway_api_key", "")
        return (
            configured
            or os.environ.get("RUNWAYML_API_SECRET", "")
            or os.environ.get("RUNWAY_API_KEY", "")
        )

def get_ai_video_config() -> dict:
    """
    Gets AI video hook configuration with safe defaults.

    Returns:
        config (dict): Sanitized AI video configuration
    """
    defaults = {
        "enabled": False,
        "provider": "runway",
        "mode": "hook_only",
        "model": "gen4.5",
        "duration": "5",
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "ratio": "720:1280",
        "poll_interval_seconds": 8,
        "timeout_seconds": 600,
    }

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("ai_video", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    poll_interval_seconds = raw_config.get(
        "poll_interval_seconds",
        defaults["poll_interval_seconds"],
    )
    timeout_seconds = raw_config.get("timeout_seconds", defaults["timeout_seconds"])

    try:
        poll_interval_seconds = int(poll_interval_seconds)
    except (TypeError, ValueError):
        poll_interval_seconds = defaults["poll_interval_seconds"]

    try:
        timeout_seconds = int(timeout_seconds)
    except (TypeError, ValueError):
        timeout_seconds = defaults["timeout_seconds"]

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "provider": str(raw_config.get("provider", defaults["provider"])).strip(),
        "mode": str(raw_config.get("mode", defaults["mode"])).strip(),
        "model": str(raw_config.get("model", defaults["model"])).strip(),
        "duration": str(raw_config.get("duration", defaults["duration"])).strip(),
        "resolution": str(raw_config.get("resolution", defaults["resolution"])).strip(),
        "aspect_ratio": str(raw_config.get("aspect_ratio", defaults["aspect_ratio"])).strip(),
        "ratio": str(raw_config.get("ratio", defaults["ratio"])).strip(),
        "poll_interval_seconds": max(3, poll_interval_seconds),
        "timeout_seconds": max(60, timeout_seconds),
    }

def get_dub_pipeline_config() -> dict:
    """
    Gets autonomous Vietnamese dubbing pipeline configuration with safe defaults.

    Returns:
        config (dict): Sanitized dubbing pipeline configuration
    """
    defaults = {
        "enabled": False,
        "sources": ["xiaohongshu"],
        "discovery_mode": "explore",
        "max_candidates": 12,
        "discovery_wait_seconds": 12,
        "discovery_login_wait_seconds": 90,
        "download_capture_wait_seconds": 18,
        "download_manual_wait_seconds": 60,
        "discovery_headless": True,
        "browser_profile": "",
        "topics": [],
        "topic_mode": "trend",
        "fallback_topic": "",
        "output_root": "output/dub_pipeline",
        "cleanup_after_successful_upload": False,
        "country": "VN",
        "language": "vi",
        "voice": "default",
        "background_mode": "duck",
        "background_volume": 0.12,
        "speech_duck_volume": 0.03,
        "ffmpeg_path": "ffmpeg",
        "ffprobe_path": "",
        "subtitles": {
            "enabled": True,
            "max_chars": 12,
            "fontsize": 70,
            "position_y": "",
        },
        "translation": {
            "primary": "gemini",
            "fallback": "groq",
            "gemini_model": "gemini-2.0-flash",
            "groq_model": "llama-3.3-70b-versatile",
            "gemini_api_key": "",
            "groq_api_key": "",
        },
        "tts": {
            "provider": "edge",
            "voice": "vi-VN-NamMinhNeural",
            "fallback_voices": ["vi-VN-HoaiMyNeural"],
            "fallback_provider": "placeholder",
            "max_speed": 1.3,
            "lucylab_api_key": "",
            "vivibe_api_key": "",
        },
        "max_video_duration_seconds": 90,
        "min_engagement": 1000,
        "source_video_path": "",
        "transcript_path": "",
        "fallback_transcript_text": "Xem hết video này nhé.",
        "upload": {
            "youtube": False,
            "tiktok": False,
            "facebook_reels": False,
        },
    }

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("dub_pipeline", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    raw_upload = raw_config.get("upload", defaults["upload"])
    if not isinstance(raw_upload, dict):
        raw_upload = defaults["upload"]

    raw_translation = raw_config.get("translation", defaults["translation"])
    if not isinstance(raw_translation, dict):
        raw_translation = defaults["translation"]

    raw_tts = raw_config.get("tts", defaults["tts"])
    if not isinstance(raw_tts, dict):
        raw_tts = defaults["tts"]

    raw_subtitles = raw_config.get("subtitles", defaults["subtitles"])
    if not isinstance(raw_subtitles, dict):
        raw_subtitles = defaults["subtitles"]

    sources = raw_config.get("sources", defaults["sources"])
    if not isinstance(sources, list):
        sources = defaults["sources"]

    topics = raw_config.get("topics", defaults["topics"])
    if not isinstance(topics, list):
        topics = defaults["topics"]

    try:
        max_candidates = int(raw_config.get("max_candidates", defaults["max_candidates"]))
    except (TypeError, ValueError):
        max_candidates = defaults["max_candidates"]

    try:
        discovery_wait_seconds = int(
            raw_config.get(
                "discovery_wait_seconds",
                defaults["discovery_wait_seconds"],
            )
        )
    except (TypeError, ValueError):
        discovery_wait_seconds = defaults["discovery_wait_seconds"]

    try:
        discovery_login_wait_seconds = int(
            raw_config.get(
                "discovery_login_wait_seconds",
                defaults["discovery_login_wait_seconds"],
            )
        )
    except (TypeError, ValueError):
        discovery_login_wait_seconds = defaults["discovery_login_wait_seconds"]

    try:
        download_capture_wait_seconds = int(
            raw_config.get(
                "download_capture_wait_seconds",
                defaults["download_capture_wait_seconds"],
            )
        )
    except (TypeError, ValueError):
        download_capture_wait_seconds = defaults["download_capture_wait_seconds"]

    try:
        download_manual_wait_seconds = int(
            raw_config.get(
                "download_manual_wait_seconds",
                defaults["download_manual_wait_seconds"],
            )
        )
    except (TypeError, ValueError):
        download_manual_wait_seconds = defaults["download_manual_wait_seconds"]

    try:
        max_duration = int(
            raw_config.get(
                "max_video_duration_seconds",
                defaults["max_video_duration_seconds"],
            )
        )
    except (TypeError, ValueError):
        max_duration = defaults["max_video_duration_seconds"]

    try:
        min_engagement = int(raw_config.get("min_engagement", defaults["min_engagement"]))
    except (TypeError, ValueError):
        min_engagement = defaults["min_engagement"]

    try:
        background_volume = float(raw_config.get("background_volume", defaults["background_volume"]))
    except (TypeError, ValueError):
        background_volume = defaults["background_volume"]

    try:
        speech_duck_volume = float(raw_config.get("speech_duck_volume", defaults["speech_duck_volume"]))
    except (TypeError, ValueError):
        speech_duck_volume = defaults["speech_duck_volume"]

    try:
        subtitle_max_chars = int(raw_subtitles.get("max_chars", defaults["subtitles"]["max_chars"]))
    except (TypeError, ValueError):
        subtitle_max_chars = defaults["subtitles"]["max_chars"]

    try:
        subtitle_fontsize = int(raw_subtitles.get("fontsize", defaults["subtitles"]["fontsize"]))
    except (TypeError, ValueError):
        subtitle_fontsize = defaults["subtitles"]["fontsize"]

    raw_subtitle_position_y = raw_subtitles.get(
        "position_y",
        defaults["subtitles"]["position_y"],
    )
    subtitle_position_y = ""
    if raw_subtitle_position_y not in ("", None):
        try:
            subtitle_position_y = int(raw_subtitle_position_y)
        except (TypeError, ValueError):
            subtitle_position_y = defaults["subtitles"]["position_y"]

    try:
        tts_max_speed = float(raw_tts.get("max_speed", defaults["tts"]["max_speed"]))
    except (TypeError, ValueError):
        tts_max_speed = defaults["tts"]["max_speed"]

    config = {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "sources": [str(source).strip() for source in sources if str(source).strip()],
        "discovery_mode": str(raw_config.get("discovery_mode", defaults["discovery_mode"])).strip(),
        "max_candidates": max(1, min(max_candidates, 50)),
        "discovery_wait_seconds": max(3, min(discovery_wait_seconds, 60)),
        "discovery_login_wait_seconds": max(0, min(discovery_login_wait_seconds, 300)),
        "download_capture_wait_seconds": max(3, min(download_capture_wait_seconds, 120)),
        "download_manual_wait_seconds": max(0, min(download_manual_wait_seconds, 180)),
        "discovery_headless": bool(
            raw_config.get("discovery_headless", defaults["discovery_headless"])
        ),
        "browser_profile": str(raw_config.get("browser_profile", defaults["browser_profile"])).strip(),
        "topics": [str(topic).strip() for topic in topics if str(topic).strip()],
        "topic_mode": str(raw_config.get("topic_mode", defaults["topic_mode"])).strip(),
        "fallback_topic": str(raw_config.get("fallback_topic", defaults["fallback_topic"])).strip(),
        "output_root": str(raw_config.get("output_root", defaults["output_root"])).strip(),
        "cleanup_after_successful_upload": bool(
            raw_config.get(
                "cleanup_after_successful_upload",
                defaults["cleanup_after_successful_upload"],
            )
        ),
        "country": str(raw_config.get("country", defaults["country"])).strip() or defaults["country"],
        "language": str(raw_config.get("language", defaults["language"])).strip() or defaults["language"],
        "voice": str(raw_config.get("voice", defaults["voice"])).strip() or defaults["voice"],
        "background_mode": str(raw_config.get("background_mode", defaults["background_mode"])).strip(),
        "background_volume": min(max(background_volume, 0.0), 1.0),
        "speech_duck_volume": min(max(speech_duck_volume, 0.0), 1.0),
        "ffmpeg_path": str(raw_config.get("ffmpeg_path", defaults["ffmpeg_path"])).strip()
        or defaults["ffmpeg_path"],
        "ffprobe_path": str(raw_config.get("ffprobe_path", defaults["ffprobe_path"])).strip(),
        "subtitles": {
            "enabled": bool(raw_subtitles.get("enabled", defaults["subtitles"]["enabled"])),
            "max_chars": max(6, min(subtitle_max_chars, 30)),
            "fontsize": max(24, min(subtitle_fontsize, 120)),
            "position_y": subtitle_position_y
            if subtitle_position_y == ""
            else max(0, min(subtitle_position_y, 1900)),
        },
        "translation": {
            "primary": str(raw_translation.get("primary", defaults["translation"]["primary"])).strip(),
            "fallback": str(raw_translation.get("fallback", defaults["translation"]["fallback"])).strip(),
            "gemini_model": str(
                raw_translation.get(
                    "gemini_model",
                    defaults["translation"]["gemini_model"],
                )
            ).strip(),
            "groq_model": str(
                raw_translation.get("groq_model", defaults["translation"]["groq_model"])
            ).strip(),
            "gemini_api_key": str(
                raw_translation.get("gemini_api_key", defaults["translation"]["gemini_api_key"])
            ).strip()
            or os.environ.get("GEMINI_API_KEY", "")
            or get_nanobanana2_api_key(),
            "groq_api_key": str(
                raw_translation.get("groq_api_key", defaults["translation"]["groq_api_key"])
            ).strip()
            or os.environ.get("GROQ_API_KEY", ""),
        },
        "tts": {
            "provider": str(raw_tts.get("provider", defaults["tts"]["provider"])).strip(),
            "voice": str(raw_tts.get("voice", defaults["tts"]["voice"])).strip(),
            "fallback_voices": [
                str(voice).strip()
                for voice in raw_tts.get(
                    "fallback_voices",
                    defaults["tts"]["fallback_voices"],
                )
                if str(voice).strip()
            ]
            if isinstance(
                raw_tts.get("fallback_voices", defaults["tts"]["fallback_voices"]),
                list,
            )
            else defaults["tts"]["fallback_voices"],
            "fallback_provider": str(
                raw_tts.get(
                    "fallback_provider",
                    defaults["tts"]["fallback_provider"],
                )
            ).strip(),
            "max_speed": min(max(tts_max_speed, 1.0), 2.0),
            "lucylab_api_key": str(
                raw_tts.get("lucylab_api_key", defaults["tts"]["lucylab_api_key"])
            ).strip()
            or os.environ.get("LUCYLAB_API_KEY", ""),
            "vivibe_api_key": str(
                raw_tts.get("vivibe_api_key", defaults["tts"]["vivibe_api_key"])
            ).strip()
            or os.environ.get("VIVIBE_API_KEY", ""),
        },
        "max_video_duration_seconds": max(5, max_duration),
        "min_engagement": max(0, min_engagement),
        "source_video_path": str(raw_config.get("source_video_path", defaults["source_video_path"])).strip(),
        "transcript_path": str(raw_config.get("transcript_path", defaults["transcript_path"])).strip(),
        "fallback_transcript_text": str(
            raw_config.get(
                "fallback_transcript_text",
                defaults["fallback_transcript_text"],
            )
        ).strip(),
        "upload": {
            "youtube": bool(raw_upload.get("youtube", defaults["upload"]["youtube"])),
            "tiktok": bool(raw_upload.get("tiktok", defaults["upload"]["tiktok"])),
            "facebook_reels": bool(
                raw_upload.get("facebook_reels", defaults["upload"]["facebook_reels"])
            ),
        },
    }
    english_mode = get_youtube_english_mode_config()
    if english_mode["enabled"]:
        config["language"] = "en"
        config["voice"] = english_mode["voice"]
        config["tts"]["voice"] = english_mode["voice"]
        config["tts"]["fallback_voices"] = english_mode["fallback_voices"]
        if not str(config["fallback_transcript_text"]).strip() or config[
            "fallback_transcript_text"
        ] == defaults["fallback_transcript_text"]:
            config["fallback_transcript_text"] = "Watch this video until the end."

    return config

def get_nanobanana2_model() -> str:
    """
    Gets the Nano Banana 2 model name.

    Returns:
        model (str): Model name
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("nanobanana2_model", "gemini-3.1-flash-image-preview")

def get_nanobanana2_aspect_ratio() -> str:
    """
    Gets the aspect ratio for Nano Banana 2 image generation.

    Returns:
        ratio (str): Aspect ratio
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("nanobanana2_aspect_ratio", "9:16")

def get_threads() -> int:
    """
    Gets the amount of threads to use for example when writing to a file with MoviePy.

    Returns:
        threads (int): Amount of threads
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["threads"]
    
def get_zip_url() -> str:
    """
    Gets the URL to the zip file containing the songs.

    Returns:
        url (str): The URL to the zip file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["zip_url"]

def get_is_for_kids() -> bool:
    """
    Gets the is for kids flag from the config file.

    Returns:
        is_for_kids (bool): The is for kids flag
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["is_for_kids"]

def get_google_maps_scraper_zip_url() -> str:
    """
    Gets the URL to the zip file containing the Google Maps scraper.

    Returns:
        url (str): The URL to the zip file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["google_maps_scraper"]

def get_google_maps_scraper_niche() -> str:
    """
    Gets the niche for the Google Maps scraper.

    Returns:
        niche (str): The niche
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["google_maps_scraper_niche"]

def get_scraper_timeout() -> int:
    """
    Gets the timeout for the scraper.

    Returns:
        timeout (int): The timeout
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["scraper_timeout"] or 300

def get_outreach_message_subject() -> str:
    """
    Gets the outreach message subject.

    Returns:
        subject (str): The outreach message subject
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["outreach_message_subject"]
    
def get_outreach_message_body_file() -> str:
    """
    Gets the outreach message body file.

    Returns:
        file (str): The outreach message body file
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["outreach_message_body_file"]

def get_tts_voice() -> str:
    """
    Gets the TTS voice from the config file.

    Returns:
        voice (str): The TTS voice
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("tts_voice", "Jasper")

def get_assemblyai_api_key() -> str:
    """
    Gets the AssemblyAI API key.

    Returns:
        key (str): The AssemblyAI API key
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["assembly_ai_api_key"]

def get_stt_provider() -> str:
    """
    Gets the configured STT provider.

    Returns:
        provider (str): The STT provider
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("stt_provider", "local_whisper")

def get_whisper_model() -> str:
    """
    Gets the local Whisper model name.

    Returns:
        model (str): Whisper model name
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_model", "base")

def get_whisper_device() -> str:
    """
    Gets the target device for Whisper inference.

    Returns:
        device (str): Whisper device
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_device", "auto")

def get_whisper_compute_type() -> str:
    """
    Gets the compute type for Whisper inference.

    Returns:
        compute_type (str): Whisper compute type
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file).get("whisper_compute_type", "int8")
    
def equalize_subtitles(srt_path: str, max_chars: int = 10) -> None:
    """
    Equalizes the subtitles in a SRT file.

    Args:
        srt_path (str): The path to the SRT file
        max_chars (int): The maximum amount of characters in a subtitle

    Returns:
        None
    """
    srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)
    
def get_font() -> str:
    """
    Gets the font from the config file.

    Returns:
        font (str): The font
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["font"]

def get_fonts_dir() -> str:
    """
    Gets the fonts directory.

    Returns:
        dir (str): The fonts directory
    """
    return os.path.join(ROOT_DIR, "fonts")

def get_imagemagick_path() -> str:
    """
    Gets the path to ImageMagick.

    Returns:
        path (str): The path to ImageMagick
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        return json.load(file)["imagemagick_path"]

def get_script_sentence_length() -> int:
    """
    Gets the forced script's sentence length.
    In case there is no sentence length in config, returns 4 when none

    Returns:
        length (int): Length of script's sentence
    """
    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)
        if (config_json.get("script_sentence_length") is not None):
            return config_json["script_sentence_length"]
        else:
            return 4

def get_post_bridge_config() -> dict:
    """
    Gets the Post Bridge configuration with safe defaults.

    Returns:
        config (dict): Sanitized Post Bridge configuration
    """
    defaults = {
        "enabled": False,
        "api_key": "",
        "platforms": ["tiktok", "instagram"],
        "account_ids": [],
        "auto_crosspost": False,
    }
    supported_platforms = {"tiktok", "instagram"}

    with open(os.path.join(ROOT_DIR, "config.json"), "r") as file:
        config_json = json.load(file)

    raw_config = config_json.get("post_bridge", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    raw_platforms = raw_config.get("platforms")
    normalized_platforms = []
    seen_platforms = set()

    if raw_platforms is None:
        normalized_platforms = defaults["platforms"].copy()
    elif isinstance(raw_platforms, list):
        for platform in raw_platforms:
            normalized_platform = str(platform).strip().lower()
            if (
                normalized_platform in supported_platforms
                and normalized_platform not in seen_platforms
            ):
                normalized_platforms.append(normalized_platform)
                seen_platforms.add(normalized_platform)
    else:
        normalized_platforms = []

    raw_account_ids = raw_config.get("account_ids", defaults["account_ids"])
    normalized_account_ids = []
    if isinstance(raw_account_ids, list):
        for account_id in raw_account_ids:
            try:
                normalized_account_ids.append(int(account_id))
            except (TypeError, ValueError):
                continue

    api_key = str(raw_config.get("api_key", "")).strip()
    if not api_key:
        api_key = os.environ.get("POST_BRIDGE_API_KEY", "").strip()

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "api_key": api_key,
        "platforms": normalized_platforms,
        "account_ids": normalized_account_ids,
        "auto_crosspost": bool(
            raw_config.get("auto_crosspost", defaults["auto_crosspost"])
        ),
    }
