# RUN THIS N AMOUNT OF TIMES
import os
import sys

from status import *
from cache import get_accounts
from config import (
    get_verbose,
    get_youtube_brand_topics_config,
    get_youtube_trends_config,
)
from classes.Tts import TTS
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from classes.TikTok import TikTok
from classes.FacebookReels import FacebookReels
from llm_provider import select_model
from post_bridge_integration import maybe_crosspost_youtube_short
from publish_checkpoint import is_published, mark_published
from auto_hashtag import build_caption
from health_check import write_health_check
from cleanup_mp import cleanup_mp_folder


def _env_flag(name: str, default: bool = True) -> bool:
    value = str(os.environ.get(name, "")).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _resolve_account(accounts: list[dict], account_id: str, account_type: str) -> dict:
    if account_id:
        for account in accounts:
            if account.get("id") == account_id:
                return account

        error(f"{account_type} account not found: {account_id}")
        available_ids = [str(account.get("id", "")) for account in accounts if account.get("id")]
        if available_ids:
            warning(f"Available {account_type} account IDs: {', '.join(available_ids)}")
        sys.exit(1)

    if accounts:
        warning(f"No {account_type} account UUID provided. Using first cached account.")
        return accounts[0]

    error(f"No cached {account_type} accounts found.")
    sys.exit(1)


def main():
    """Main function to post content to Twitter or upload videos to YouTube.

    This function determines its operation based on command-line arguments:
    - If the purpose is "twitter", it initializes a Twitter account and posts a message.
    - If the purpose is "youtube", it initializes a YouTube account, generates a video with TTS, and uploads it.
    - If the purpose is "tiktok", it initializes a TikTok account and uploads a video.
    - If the purpose is "facebook_reels", it initializes a Facebook Reels account and uploads a video.

    Command-line arguments:
        sys.argv[1]: A string indicating the purpose, either "twitter", "youtube", "tiktok", or "facebook_reels".
        sys.argv[2]: A string representing the account UUID.

    The function also handles verbose output based on user settings and reports success or errors as appropriate.

    Args:
        None. The function uses command-line arguments accessed via sys.argv.

    Returns:
        None. The function performs operations based on the purpose and account UUID and does not return any value."""
    purpose = str(sys.argv[1])
    account_id = str(sys.argv[2])
    model = str(sys.argv[3]) if len(sys.argv) > 3 else None

    if model:
        select_model(model)
    else:
        error("No Ollama model specified. Pass model name as third argument.")
        sys.exit(1)

    verbose = get_verbose()
    brand_topics_config = get_youtube_brand_topics_config()
    trends_config = get_youtube_trends_config()
    info(
        "Cron topic source: "
        f"youtube_brand_topics.enabled={brand_topics_config['enabled']}, "
        f"youtube_trends.enabled={trends_config['enabled']}, "
        f"source={trends_config['source']}, "
        f"geo={trends_config['geo']}, "
        f"hl={trends_config['hl']}"
    )

    if purpose == "twitter":
        accounts = get_accounts("twitter")
        acc = _resolve_account(accounts, account_id, "twitter")
        if verbose:
            info("Initializing Twitter...")
        twitter = Twitter(
            acc["id"],
            acc["nickname"],
            acc["firefox_profile"],
            acc["topic"]
        )
        twitter.post()
        if verbose:
            success("Done posting.")
    elif purpose == "youtube":
        tts = TTS()

        accounts = get_accounts("youtube")
        acc = _resolve_account(accounts, account_id, "youtube")
        if verbose:
            info("Initializing YouTube...")
        youtube = YouTube(
            acc["id"],
            acc["nickname"],
            acc["firefox_profile"],
            acc["niche"],
            acc["language"]
        )
        youtube.generate_video(tts)
        upload_success = youtube.upload_video()
        if upload_success:
            youtube_success = True
            tiktok_success = False
            facebook_success = False
            cleanup_mp_folder(max_age_hours=6)
            if verbose:
                success("Uploaded Short.")

            tiktok_caption = build_caption(
                youtube.metadata.get("title", ""),
                youtube.metadata.get("description", ""),
            )

            if _env_flag("MPV2_UPLOAD_TIKTOK", True):
                try:
                    if verbose:
                        info("Initializing TikTok...")

                    tiktok = TikTok(acc["firefox_profile"])
                    if is_published(youtube.video_path, "tiktok"):
                        warning("TikTok already published. Skipping.")
                        tiktok_success = True
                    else:
                        tiktok_success = tiktok.upload_video(
                            youtube.video_path,
                            tiktok_caption,
                        )

                        if tiktok_success:
                            mark_published(youtube.video_path, "tiktok")

                    if tiktok_success:
                        if verbose:
                            success("Uploaded TikTok.")
                    else:
                        warning("TikTok upload failed.")

                except Exception as e:
                    warning(f"TikTok upload failed: {e}")
            else:
                info("Skipping TikTok upload for this scheduler slot.")

            if _env_flag("MPV2_UPLOAD_FACEBOOK_REELS", True):
                try:
                    if verbose:
                        info("Initializing Facebook Profile Reels...")

                    facebook_reels = FacebookReels(acc["firefox_profile"])
                    if is_published(youtube.video_path, "facebook_profile"):
                        warning("Facebook Profile Reel already published. Skipping.")
                        facebook_success = True
                    else:
                        facebook_success = facebook_reels.upload_profile_reel(
                            youtube.video_path,
                            tiktok_caption,
                        )

                        if facebook_success:
                            mark_published(youtube.video_path, "facebook_profile")

                    if facebook_success:
                        if verbose:
                            success("Uploaded Facebook Profile Reel.")
                    else:
                        warning("Facebook Profile Reel upload failed.")

                except Exception as e:
                    warning(f"Facebook Profile Reel upload failed: {e}")
            else:
                info("Skipping Facebook Profile Reel upload for this scheduler slot.")

            write_health_check(
                video_path=youtube.video_path,
                youtube=youtube_success,
                tiktok=tiktok_success,
                facebook_profile=facebook_success,
            )

            maybe_crosspost_youtube_short(
                video_path=youtube.video_path,
                title=youtube.metadata.get("title", ""),
                interactive=False,
            )

        else:
            write_health_check(
                video_path=getattr(youtube, "video_path", ""),
                youtube=False,
                tiktok=False,
                facebook_profile=False,
            )
            warning("YouTube upload failed. Skipping Post Bridge cross-post.")
    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
