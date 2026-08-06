#!/usr/bin/env python3
import json
import os
import shutil
import sys
from typing import Tuple

import requests


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
YOUTUBE_CACHE_PATH = os.path.join(ROOT_DIR, ".mp", "youtube.json")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def check_url(url: str, timeout: int = 3) -> Tuple[bool, str]:
    try:
        response = requests.get(url, timeout=timeout)
        return True, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def get_cached_youtube_firefox_profile() -> str:
    if not os.path.exists(YOUTUBE_CACHE_PATH):
        return ""

    try:
        with open(YOUTUBE_CACHE_PATH, "r", encoding="utf-8") as file:
            parsed = json.load(file)
    except Exception:
        return ""

    accounts = parsed.get("accounts", [])
    if not isinstance(accounts, list):
        return ""

    for account in accounts:
        if not isinstance(account, dict):
            continue

        firefox_profile = str(account.get("firefox_profile", "")).strip()
        if firefox_profile and os.path.isdir(firefox_profile):
            return firefox_profile

    return ""


def main() -> int:
    if not os.path.exists(CONFIG_PATH):
        fail(f"Missing config file: {CONFIG_PATH}")
        return 1

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    failures = 0

    stt_provider = str(cfg.get("stt_provider", "local_whisper")).lower()

    ok(f"stt_provider={stt_provider}")

    imagemagick_path = cfg.get("imagemagick_path", "")
    if imagemagick_path and os.path.exists(imagemagick_path):
        ok(f"imagemagick_path exists: {imagemagick_path}")
    else:
        warn(
            "imagemagick_path is not set to a valid executable path. "
            "MoviePy subtitle rendering may fail."
        )

    firefox_profile = cfg.get("firefox_profile", "")
    if firefox_profile:
        if os.path.isdir(firefox_profile):
            ok(f"firefox_profile exists: {firefox_profile}")
        else:
            warn(f"firefox_profile does not exist: {firefox_profile}")
    else:
        warn("firefox_profile is empty. Twitter/YouTube automation requires this.")

    # Ollama (LLM)
    base = str(cfg.get("ollama_base_url", "http://127.0.0.1:11434")).rstrip("/")
    reachable, detail = check_url(f"{base}/api/tags")
    if not reachable:
        fail(f"Ollama is not reachable at {base}: {detail}")
        failures += 1
    else:
        ok(f"Ollama reachable at {base}")
        try:
            tags = requests.get(f"{base}/api/tags", timeout=5).json()
            models = [m.get("name") for m in tags.get("models", [])]
            if models:
                ok(f"Ollama models available: {', '.join(models[:10])}")
            else:
                warn("No models found on Ollama. Pull a model first (e.g. 'ollama pull llama3.2:3b').")
        except Exception as exc:
            warn(f"Could not validate Ollama model list: {exc}")

    # Nano Banana 2 (image generation)
    api_key = cfg.get("nanobanana2_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    nb2_base = str(
        cfg.get(
            "nanobanana2_api_base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        )
    ).rstrip("/")
    if api_key:
        ok("nanobanana2_api_key is set")
    else:
        fail("nanobanana2_api_key is empty (and GEMINI_API_KEY is not set)")
        failures += 1

    reachable, detail = check_url(nb2_base, timeout=8)
    if not reachable:
        warn(f"Nano Banana 2 base URL could not be reached: {detail}")
    else:
        ok(f"Nano Banana 2 base URL reachable: {nb2_base}")

    if stt_provider == "local_whisper":
        try:
            import faster_whisper  # noqa: F401

            ok("faster-whisper is installed")
        except Exception as exc:
            fail(f"faster-whisper is not importable: {exc}")
            failures += 1

    dub_pipeline = cfg.get("dub_pipeline", {})
    if isinstance(dub_pipeline, dict) and dub_pipeline.get("enabled"):
        ok("dub_pipeline.enabled=true")

        ffmpeg_path = str(dub_pipeline.get("ffmpeg_path", "ffmpeg")).strip() or "ffmpeg"
        resolved_ffmpeg = ffmpeg_path if os.path.isabs(ffmpeg_path) else shutil.which(ffmpeg_path)
        if resolved_ffmpeg and os.path.exists(resolved_ffmpeg):
            ok(f"ffmpeg is available for dub pipeline: {resolved_ffmpeg}")
        else:
            fail(
                "ffmpeg is required for dub pipeline render/audio steps. "
                "Install ffmpeg or set dub_pipeline.ffmpeg_path."
            )
            failures += 1

        ffprobe_path = str(dub_pipeline.get("ffprobe_path", "")).strip()
        if not ffprobe_path and resolved_ffmpeg:
            ffprobe_path = resolved_ffmpeg.replace("ffmpeg", "ffprobe")
        resolved_ffprobe = (
            ffprobe_path if os.path.isabs(ffprobe_path) else shutil.which(ffprobe_path)
        )
        if resolved_ffprobe and os.path.exists(resolved_ffprobe):
            ok(f"ffprobe is available for dub pipeline: {resolved_ffprobe}")
        else:
            fail(
                "ffprobe is required for dub pipeline media validation. "
                "Install ffmpeg or set dub_pipeline.ffprobe_path."
            )
            failures += 1

        source_video_path = str(dub_pipeline.get("source_video_path", "")).strip()
        if source_video_path:
            if os.path.exists(source_video_path):
                ok(f"dub_pipeline.source_video_path exists: {source_video_path}")
            else:
                fail(f"dub_pipeline.source_video_path does not exist: {source_video_path}")
                failures += 1
        else:
            ok("dub_pipeline.source_video_path is empty; discovery/download will be used")
            try:
                import yt_dlp  # noqa: F401

                ok("yt-dlp Python module is available for discovered source download")
            except Exception:
                if shutil.which("yt-dlp"):
                    ok("yt-dlp binary is available for discovered source download")
                else:
                    fail(
                        "yt-dlp is required when dub_pipeline.source_video_path is empty. "
                        "Install it with `brew install yt-dlp` or `pip install yt-dlp`."
                    )
                    failures += 1

            browser_profile = str(dub_pipeline.get("browser_profile", "")).strip()
            if browser_profile:
                if os.path.isdir(browser_profile):
                    ok(f"dub_pipeline.browser_profile exists: {browser_profile}")
                else:
                    fail(f"dub_pipeline.browser_profile does not exist: {browser_profile}")
                    failures += 1

        transcript_path = str(dub_pipeline.get("transcript_path", "")).strip()
        if transcript_path:
            if os.path.exists(transcript_path):
                ok(f"dub_pipeline.transcript_path exists: {transcript_path}")
            else:
                fail(f"dub_pipeline.transcript_path does not exist: {transcript_path}")
                failures += 1
        else:
            try:
                import faster_whisper  # noqa: F401

                ok("dub_pipeline.transcript_path is empty; local Whisper ASR will be used")
            except Exception as exc:
                fail(
                    "dub_pipeline.transcript_path is empty and faster-whisper is "
                    f"not importable: {exc}"
                )
                failures += 1

        output_root = str(dub_pipeline.get("output_root", "output/dub_pipeline")).strip()
        if not os.path.isabs(output_root):
            output_root = os.path.join(ROOT_DIR, output_root)
        try:
            os.makedirs(output_root, exist_ok=True)
            ok(f"dub_pipeline.output_root is writable: {output_root}")
        except Exception as exc:
            fail(f"dub_pipeline.output_root is not writable: {exc}")
            failures += 1

        upload = dub_pipeline.get("upload", {})
        if isinstance(upload, dict) and any(upload.values()):
            dub_browser_profile = str(dub_pipeline.get("browser_profile", "")).strip()
            cached_youtube_profile = get_cached_youtube_firefox_profile()
            upload_profile = dub_browser_profile or firefox_profile or cached_youtube_profile

            if upload_profile and os.path.isdir(upload_profile):
                ok(f"dub_pipeline upload enabled and Firefox profile exists: {upload_profile}")
            else:
                fail(
                    "dub_pipeline upload is enabled but no valid Firefox profile was found "
                    "in dub_pipeline.browser_profile, firefox_profile, or cached YouTube account"
                )
                failures += 1

    if failures:
        print("")
        print(f"Preflight completed with {failures} blocking issue(s).")
        return 1

    print("")
    print("Preflight passed. Local setup looks ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
