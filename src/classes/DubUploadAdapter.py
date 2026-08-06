import json
import os
import re

from cache import get_accounts
from publish_checkpoint import is_published, mark_published
from status import info, success, warning
from .FacebookReels import FacebookReels
from .DubMetadata import DubMetadata
from .TikTok import TikTok
from .YouTube import YouTube


class DubUploadAdapter:
    def __init__(self, config: dict, account_id: str = "") -> None:
        self.config = config
        self.account_id = account_id

    def upload(self, video_path: str, metadata_path: str, caption_path: str, run_dir: str) -> dict:
        upload_config = self._apply_env_upload_overrides(self.config.get("upload", {}))
        with open(metadata_path, "r", encoding="utf-8") as file:
            metadata = json.load(file)
        with open(caption_path, "r", encoding="utf-8") as file:
            caption = file.read().strip()

        result = {
            "youtube": self._skipped_result("youtube", upload_config),
            "tiktok": self._skipped_result("tiktok", upload_config),
            "facebook_reels": self._skipped_result("facebook_reels", upload_config),
        }

        if not any(upload_config.values()):
            self._write_result(run_dir, result)
            info(" => Dub upload disabled; wrote upload_result.json.")
            return result

        account = self._find_youtube_account()

        if upload_config.get("youtube"):
            result["youtube"] = self._upload_youtube(account, video_path, metadata)

        if upload_config.get("tiktok"):
            result["tiktok"] = self._upload_tiktok(account, video_path, caption)

        if upload_config.get("facebook_reels"):
            result["facebook_reels"] = self._upload_facebook_reels(account, video_path, caption)

        self._write_result(run_dir, result)
        return result

    @staticmethod
    def _env_flag(name: str, default: bool) -> bool:
        value = str(os.environ.get(name, "")).strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        return default

    @classmethod
    def _apply_env_upload_overrides(cls, upload_config: dict) -> dict:
        config = dict(upload_config or {})
        config["youtube"] = cls._env_flag(
            "MPV2_DUB_UPLOAD_YOUTUBE",
            bool(config.get("youtube")),
        )
        config["tiktok"] = cls._env_flag(
            "MPV2_DUB_UPLOAD_TIKTOK",
            bool(config.get("tiktok")),
        )
        config["facebook_reels"] = cls._env_flag(
            "MPV2_DUB_UPLOAD_FACEBOOK_REELS",
            bool(config.get("facebook_reels")),
        )
        return config

    @staticmethod
    def _skipped_result(platform: str, upload_config: dict) -> dict:
        if upload_config.get(platform):
            return {"enabled": True, "success": False, "error": "not attempted"}
        return {"enabled": False, "success": True, "skipped": True}

    def _find_youtube_account(self) -> dict:
        accounts = get_accounts("youtube")
        if not accounts:
            raise RuntimeError("No YouTube accounts configured in cache")

        if not self.account_id:
            return accounts[0]

        for account in accounts:
            if account.get("id") == self.account_id:
                return account

        raise RuntimeError(f"YouTube account not found: {self.account_id}")

    def _upload_youtube(self, account: dict, video_path: str, metadata: dict) -> dict:
        platform = "youtube"
        title = str(metadata.get("title", "")).strip()
        description = str(metadata.get("description", "")).strip()
        if not DubMetadata._is_good_title(title) or DubMetadata._is_generic_title(title):
            message = f"Refusing YouTube upload with invalid or generic dub title: {title!r}"
            warning(message)
            return {"enabled": True, "success": False, "error": message}
        if DubMetadata._contains_chinese(title) or DubMetadata._contains_chinese(description):
            message = "Refusing YouTube upload with Chinese text in dub title or description"
            warning(message)
            return {"enabled": True, "success": False, "error": message}
        if self._is_duplicate_youtube_title(account, title):
            message = f"Refusing YouTube upload with duplicate dub title: {title!r}"
            warning(message)
            return {"enabled": True, "success": False, "error": message}

        if is_published(video_path, platform):
            warning("YouTube already published for this dubbed video. Skipping.")
            return {"enabled": True, "success": True, "skipped": True}

        try:
            youtube = YouTube(
                account["id"],
                account["nickname"],
                account["firefox_profile"],
                account["niche"],
                account["language"],
            )
            youtube.video_path = os.path.abspath(video_path)
            youtube.metadata = {
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
            }
            uploaded = youtube.upload_video()
            if uploaded:
                mark_published(video_path, platform)
                success(" => Uploaded dubbed video to YouTube.")
            return {
                "enabled": True,
                "success": uploaded,
                "url": getattr(youtube, "uploaded_video_url", ""),
            }
        except Exception as exc:
            return {"enabled": True, "success": False, "error": str(exc)}

    @classmethod
    def _is_duplicate_youtube_title(cls, account: dict, title: str) -> bool:
        normalized_title = cls._normalize_title(title)
        if not normalized_title:
            return False

        return any(
            cls._normalize_title(video.get("title", "")) == normalized_title
            for video in account.get("videos", [])
            if isinstance(video, dict)
        )

    @staticmethod
    def _normalize_title(title: object) -> str:
        normalized = str(title or "").casefold().replace("'", "").replace("’", "")
        normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
        return re.sub(r"\s+", " ", normalized).strip()

    def _upload_tiktok(self, account: dict, video_path: str, caption: str) -> dict:
        platform = "tiktok"
        if DubMetadata._contains_chinese(caption):
            message = "Refusing TikTok upload with Chinese text in dub caption"
            warning(message)
            return {"enabled": True, "success": False, "error": message}
        if is_published(video_path, platform):
            warning("TikTok already published for this dubbed video. Skipping.")
            return {"enabled": True, "success": True, "skipped": True}

        try:
            uploaded = TikTok(account["firefox_profile"]).upload_video(video_path, caption)
            if uploaded:
                mark_published(video_path, platform)
            return {"enabled": True, "success": uploaded}
        except Exception as exc:
            return {"enabled": True, "success": False, "error": str(exc)}

    def _upload_facebook_reels(self, account: dict, video_path: str, caption: str) -> dict:
        platform = "facebook_reels"
        if DubMetadata._contains_chinese(caption):
            message = "Refusing Facebook Reels upload with Chinese text in dub caption"
            warning(message)
            return {"enabled": True, "success": False, "error": message}
        if is_published(video_path, platform):
            warning("Facebook Reels already published for this dubbed video. Skipping.")
            return {"enabled": True, "success": True, "skipped": True}

        try:
            uploaded = FacebookReels(account["firefox_profile"]).upload_profile_reel(
                video_path,
                caption,
            )
            if uploaded:
                mark_published(video_path, platform)
            return {"enabled": True, "success": uploaded}
        except Exception as exc:
            return {"enabled": True, "success": False, "error": str(exc)}

    @staticmethod
    def _write_result(run_dir: str, result: dict) -> None:
        with open(os.path.join(run_dir, "upload_result.json"), "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
