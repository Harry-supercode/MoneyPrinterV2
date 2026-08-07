#!/usr/bin/env python3
import argparse
import glob
import json
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from classes.FacebookReels import FacebookReels
from classes.TikTok import TikTok


def latest_mp4() -> str:
    candidates = glob.glob(os.path.join(ROOT_DIR, ".mp", "*.mp4"))
    if not candidates:
        raise RuntimeError("No .mp/*.mp4 video found")
    return max(candidates, key=os.path.getmtime)


def first_youtube_account() -> dict:
    path = os.path.join(ROOT_DIR, ".mp", "youtube.json")
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    accounts = data.get("accounts", [])
    if not accounts:
        raise RuntimeError("No account found in .mp/youtube.json")
    return accounts[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload the latest MPV2 video to TikTok/Facebook.")
    parser.add_argument(
        "--platform",
        choices=["tiktok", "facebook", "both"],
        default="both",
    )
    parser.add_argument("--video", default="", help="Explicit video path. Defaults to latest .mp/*.mp4.")
    parser.add_argument(
        "--caption",
        default="Test upload from MoneyPrinterV2 #hiemee #business #technology",
    )
    args = parser.parse_args()

    account = first_youtube_account()
    profile = account.get("firefox_profile", "")
    if not profile:
        raise RuntimeError("Account firefox_profile is empty")

    video_path = os.path.abspath(args.video or latest_mp4())
    print(f"Using profile: {profile}")
    print(f"Using video: {video_path}")

    if args.platform in {"tiktok", "both"}:
        print("Uploading to TikTok...")
        if not TikTok(profile).upload_video(video_path, args.caption):
            return 1

    if args.platform in {"facebook", "both"}:
        print("Uploading to Facebook Reels...")
        if not FacebookReels(profile).upload_profile_reel(video_path, args.caption):
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
