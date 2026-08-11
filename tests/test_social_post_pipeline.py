import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from classes.SocialPostPipeline import SocialPostPipeline


class SocialPostPipelineDraftTests(unittest.TestCase):
    def test_dry_run_can_use_existing_reviewed_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            draft_path = Path(temp_dir) / "draft.json"
            draft_path.write_text(
                json.dumps(
                    {
                        "id": "reviewed",
                        "text": "Reviewed text",
                        "image_path": "",
                    }
                ),
                encoding="utf-8",
            )

            with patch("classes.SocialPostPipeline.get_social_posts_config") as config:
                config.return_value = {
                    "enabled": True,
                    "automation_verified": False,
                    "platforms": {"facebook": {"enabled": True}},
                }
                result = SocialPostPipeline().run(
                    platform="facebook",
                    dry_run=True,
                    draft_path=str(draft_path),
                )

        self.assertEqual(result["draft"]["text"], "Reviewed text")
        self.assertTrue(result["dry_run"])

    def test_duplicate_skip_is_not_reported_as_publish_success(self) -> None:
        with patch("classes.SocialPostPipeline.get_social_posts_config") as config:
            config.return_value = {
                "enabled": True,
                "automation_verified": True,
                "browser_profile": "/tmp/profile",
                "platforms": {"facebook": {"enabled": True}},
            }
            pipeline = SocialPostPipeline()
            with patch.object(pipeline, "_already_published", return_value=True):
                result = pipeline._publish_platform(
                    "facebook",
                    {"text": "Reviewed text", "image_path": ""},
                )

        self.assertFalse(result["success"])
        self.assertTrue(result["skipped_duplicate"])


if __name__ == "__main__":
    unittest.main()
