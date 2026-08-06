import json
import os
import random
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from config import ROOT_DIR, get_youtube_brand_topics_config, get_youtube_trends_config
from status import info, warning


GOOGLE_TRENDS_RSS_URL = "https://trends.google.com/trending/rss"
GOOGLE_TRENDS_CACHE_PATH = os.path.join(ROOT_DIR, ".mp", "google_trends_cache.json")


def normalize_for_safety(value: str) -> str:
    value = (value or "").replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", value)
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_marks.lower().split())


def find_unsafe_keyword(keyword: str, unsafe_keywords: list[str]) -> str:
    normalized_keyword = normalize_for_safety(keyword)

    for unsafe_keyword in unsafe_keywords:
        normalized_unsafe = normalize_for_safety(unsafe_keyword)
        if normalized_unsafe and normalized_unsafe in normalized_keyword:
            return unsafe_keyword

    return ""


def filter_safe_trend_keywords(
    keywords: list[str],
    unsafe_keywords: list[str],
) -> list[str]:
    safe_keywords = []

    for keyword in keywords:
        matched_unsafe_keyword = find_unsafe_keyword(keyword, unsafe_keywords)
        if matched_unsafe_keyword:
            warning(
                f"Skipping unsafe Google Trends keyword: {keyword} "
                f"(matched: {matched_unsafe_keyword})"
            )
            continue

        safe_keywords.append(keyword)

    return safe_keywords


def fetch_google_trends_keywords(
    geo: str,
    hl: str,
    category_filter: str = "",
    max_items: int = 10,
) -> list[str]:
    """
    Fetches daily trending search terms from Google Trends RSS.
    """
    response = requests.get(
        GOOGLE_TRENDS_RSS_URL,
        params={"geo": geo, "hl": hl},
        timeout=(3.05, 8),
    )
    response.raise_for_status()

    root = ET.fromstring(response.text)
    keywords = []
    normalized_filter = category_filter.strip().lower()

    for item in root.findall("./channel/item"):
        title = item.findtext("title", default="").strip()
        if not title:
            continue

        if normalized_filter and normalized_filter not in title.lower():
            description = item.findtext("description", default="").lower()
            if normalized_filter not in description:
                continue

        keywords.append(title)
        if len(keywords) >= max_items:
            break

    if keywords:
        _write_trends_cache(keywords, geo, hl, category_filter)

    return keywords


def _write_trends_cache(
    keywords: list[str],
    geo: str,
    hl: str,
    category_filter: str,
) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "geo": geo,
        "hl": hl,
        "category_filter": category_filter,
        "keywords": keywords,
    }
    try:
        os.makedirs(os.path.dirname(GOOGLE_TRENDS_CACHE_PATH), exist_ok=True)
        with open(GOOGLE_TRENDS_CACHE_PATH, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        warning(f"Could not write Google Trends cache: {exc}")


def _read_trends_cache(
    geo: str,
    hl: str,
    category_filter: str,
    max_items: int,
) -> list[str]:
    try:
        with open(GOOGLE_TRENDS_CACHE_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, ValueError, TypeError):
        return []

    if payload.get("geo") != geo or payload.get("hl") != hl:
        return []
    if payload.get("category_filter", "") != category_filter:
        return []

    keywords = payload.get("keywords", [])
    if not isinstance(keywords, list):
        return []
    return [str(keyword).strip() for keyword in keywords if str(keyword).strip()][
        :max_items
    ]


def get_trend_topic_seed(fallback_niche: str) -> str:
    """
    Returns a trend keyword seed for YouTube topic generation, or fallback niche.
    """
    trends_config = get_youtube_trends_config()
    if not trends_config["enabled"]:
        return fallback_niche

    if trends_config["source"] not in {"google_trending_rss", "google_trends_rss"}:
        warning(
            f"Unsupported youtube_trends source '{trends_config['source']}'. "
            "Falling back to account niche."
        )
        return fallback_niche

    try:
        keywords = fetch_google_trends_keywords(
            geo=trends_config["geo"],
            hl=trends_config["hl"],
            category_filter=trends_config["category_filter"],
            max_items=trends_config["max_items"],
        )
    except Exception as exc:
        keywords = _read_trends_cache(
            geo=trends_config["geo"],
            hl=trends_config["hl"],
            category_filter=trends_config["category_filter"],
            max_items=trends_config["max_items"],
        )
        if keywords:
            warning(f"Could not fetch Google Trends; using cached trends instead: {exc}")
        else:
            warning(f"Could not fetch Google Trends. Falling back to account niche: {exc}")
            return fallback_niche

    if trends_config.get("safety_filter_enabled", True):
        keywords = filter_safe_trend_keywords(
            keywords=keywords,
            unsafe_keywords=trends_config.get("unsafe_keywords", []),
        )

    if not keywords:
        warning(
            "Google Trends returned no safe usable keywords. "
            "Falling back to account niche."
        )
        return fallback_niche

    selected_keyword = random.choice(keywords)
    info(f"Using Google Trends keyword for topic seed: {selected_keyword}")
    return selected_keyword


def get_brand_topic_seed(fallback_niche: str) -> str:
    """
    Returns a brand-safe HIEMEE topic seed, or fallback niche.
    """
    brand_config = get_youtube_brand_topics_config()
    if not brand_config["enabled"]:
        return fallback_niche

    topic_pool = brand_config["concepts"] + brand_config["keywords"]
    if not topic_pool:
        warning("youtube_brand_topics is enabled but empty. Falling back to account niche.")
        return fallback_niche

    selected_topic = random.choice(topic_pool)
    info(f"Using HIEMEE brand topic seed: {selected_topic}")
    return selected_topic


def get_youtube_topic_seed(fallback_niche: str) -> str:
    """
    Returns the YouTube Shorts topic seed.

    Brand topics take precedence over Google Trends so cron can stay focused on
    the HIEMEE ecosystem while the trend feature is temporarily disabled.
    """
    brand_config = get_youtube_brand_topics_config()
    if brand_config["enabled"]:
        return get_brand_topic_seed(fallback_niche)

    return get_trend_topic_seed(fallback_niche)
