import hashlib
import json
from datetime import datetime
from pathlib import Path

from config import ROOT_DIR, get_social_posts_config
from status import info, success, warning
from .FacebookPost import FacebookPost
from .SocialPostGenerator import SocialPostGenerator
from .YouTubeCommunityPost import YouTubeCommunityPost


class SocialPostPipeline:
    def __init__(self) -> None:
        self.config = get_social_posts_config()
        self.state_path = Path(ROOT_DIR) / ".mp" / "social_posts_state.json"

    def run(
        self,
        platform: str = "all",
        dry_run: bool = False,
        allow_unverified: bool = False,
        draft_path: str = "",
    ) -> dict:
        if not self.config.get("enabled"):
            raise RuntimeError("social_posts.enabled is false")

        if not dry_run and not allow_unverified and not self.config.get("automation_verified"):
            raise RuntimeError(
                "Refusing social post publish because social_posts.automation_verified is false. "
                "Run and verify browser automation on the VPS first, then set it true."
            )

        draft = self._load_draft(draft_path) if draft_path else SocialPostGenerator(self.config).generate()
        result = {
            "draft": draft,
            "dry_run": dry_run,
            "platforms": {},
        }
        info(f" => Social post draft ready: {draft.get('draft_path', draft_path)}")

        if dry_run:
            self._record_result(result)
            success(" => Social post dry run complete; no platform publish attempted.")
            return result

        targets = self._target_platforms(platform)
        for target in targets:
            result["platforms"][target] = self._publish_platform(target, draft)

        self._record_result(result)
        if any(item.get("success") for item in result["platforms"].values()):
            success(" => Social post pipeline complete.")
        else:
            warning(" => Social post pipeline completed without successful publishes.")
        return result

    def _load_draft(self, draft_path: str) -> dict:
        path = Path(draft_path).expanduser()
        if not path.is_absolute():
            path = Path(ROOT_DIR) / path
        if not path.exists():
            raise FileNotFoundError(f"Social post draft not found: {path}")

        with path.open("r", encoding="utf-8") as file:
            draft = json.load(file)

        if not isinstance(draft, dict):
            raise ValueError(f"Social post draft must be a JSON object: {path}")

        text = str(draft.get("text", "")).strip()
        if not text:
            raise ValueError(f"Social post draft text is empty: {path}")

        image_path = str(draft.get("image_path", "")).strip()
        if image_path and not Path(image_path).expanduser().exists():
            raise FileNotFoundError(f"Social post draft image not found: {image_path}")

        draft["draft_path"] = str(path)
        draft.setdefault("id", path.stem)
        return draft

    def _target_platforms(self, platform: str) -> list[str]:
        requested = str(platform or "all").strip().lower()
        available = ["facebook", "youtube"]
        if requested != "all":
            if requested not in available:
                raise ValueError(f"Unsupported social post platform: {platform}")
            available = [requested]

        platforms = self.config.get("platforms", {})
        return [
            name
            for name in available
            if bool(platforms.get(name, {}).get("enabled", False))
        ]

    def _publish_platform(self, platform: str, draft: dict) -> dict:
        fingerprint = self._fingerprint(platform, draft)
        if self._already_published(fingerprint):
            warning(f" => Skipping duplicate {platform} social post.")
            return {"enabled": True, "success": True, "skipped_duplicate": True}

        browser_profile = str(self.config.get("browser_profile", "")).strip()
        if not browser_profile:
            raise RuntimeError("social_posts.browser_profile is empty")

        platform_config = self.config.get("platforms", {}).get(platform, {})
        create_url = str(platform_config.get("create_url", "")).strip()
        wait_seconds = int(platform_config.get("post_wait_seconds", 12))

        if platform == "facebook":
            publisher = FacebookPost(browser_profile, create_url, wait_seconds)
        elif platform == "youtube":
            publisher = YouTubeCommunityPost(browser_profile, create_url, wait_seconds)
        else:
            raise ValueError(f"Unsupported social post platform: {platform}")

        success_value = publisher.publish(draft["text"], draft.get("image_path", ""))
        if success_value:
            self._mark_published(fingerprint)

        return {"enabled": True, "success": success_value}

    def _record_result(self, result: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = self._load_state()
        runs = state.setdefault("runs", [])
        runs.append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "draft_id": result["draft"]["id"],
                "draft_path": result["draft"].get("draft_path", ""),
                "dry_run": result["dry_run"],
                "platforms": result["platforms"],
            }
        )
        state["runs"] = runs[-100:]
        self._save_state(state)

    def _load_state(self) -> dict:
        try:
            with self.state_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_state(self, state: dict) -> None:
        tmp_path = self.state_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        tmp_path.replace(self.state_path)

    def _fingerprint(self, platform: str, draft: dict) -> str:
        text = str(draft.get("text", "")).strip()
        image_path = str(draft.get("image_path", "")).strip()
        return hashlib.sha256(f"{platform}\n{text}\n{image_path}".encode("utf-8")).hexdigest()

    def _already_published(self, fingerprint: str) -> bool:
        state = self._load_state()
        published = state.get("published", [])
        return fingerprint in published

    def _mark_published(self, fingerprint: str) -> None:
        state = self._load_state()
        published = state.setdefault("published", [])
        if fingerprint not in published:
            published.append(fingerprint)
        state["published"] = published[-1000:]
        self._save_state(state)
