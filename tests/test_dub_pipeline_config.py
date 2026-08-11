import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import config


class DubPipelineConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_dub_pipeline_uses_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                dub_config = config.get_dub_pipeline_config()

        self.assertFalse(dub_config["enabled"])
        self.assertEqual(dub_config["topics"], [])
        self.assertEqual(dub_config["topic_mode"], "trend")
        self.assertEqual(dub_config["output_root"], "output/dub_pipeline")
        self.assertEqual(dub_config["language"], "vi")
        self.assertEqual(dub_config["ffmpeg_path"], "ffmpeg")
        self.assertFalse(dub_config["upload"]["youtube"])

    def test_dub_pipeline_normalizes_bounds_and_upload_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "dub_pipeline": {
                        "enabled": True,
                        "sources": "xiaohongshu",
                        "topics": "review",
                        "background_volume": "2.0",
                        "max_video_duration_seconds": "3",
                        "min_engagement": "-5",
                        "upload": {
                            "youtube": True,
                            "tiktok": False,
                            "facebook_reels": True,
                        },
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                dub_config = config.get_dub_pipeline_config()

        self.assertTrue(dub_config["enabled"])
        self.assertEqual(dub_config["sources"], ["xiaohongshu"])
        self.assertEqual(dub_config["fallback_source_urls"], [])
        self.assertEqual(dub_config["topics"], [])
        self.assertEqual(dub_config["background_volume"], 1.0)
        self.assertEqual(dub_config["max_video_duration_seconds"], 5)
        self.assertEqual(dub_config["min_engagement"], 0)
        self.assertTrue(dub_config["upload"]["youtube"])
        self.assertFalse(dub_config["upload"]["tiktok"])
        self.assertTrue(dub_config["upload"]["facebook_reels"])

    def test_dub_pipeline_preserves_fallback_source_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "dub_pipeline": {
                        "fallback_source_urls": [
                            " https://www.youtube.com/watch?v=abc123 ",
                            "",
                            "https://example.com/video.mp4",
                        ],
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                dub_config = config.get_dub_pipeline_config()

        self.assertEqual(
            dub_config["fallback_source_urls"],
            [
                "https://www.youtube.com/watch?v=abc123",
                "https://example.com/video.mp4",
            ],
        )

    def test_youtube_english_mode_overrides_dub_language_and_tts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "youtube_english_mode": {
                        "enabled": True,
                        "voice": "en-GB-RyanNeural",
                        "fallback_voices": ["en-US-JennyNeural"],
                    },
                    "dub_pipeline": {
                        "enabled": True,
                        "language": "vi",
                        "tts": {
                            "voice": "vi-VN-NamMinhNeural",
                            "fallback_voices": ["vi-VN-HoaiMyNeural"],
                        },
                    },
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                dub_config = config.get_dub_pipeline_config()

        self.assertEqual(dub_config["language"], "en")
        self.assertEqual(dub_config["voice"], "en-GB-RyanNeural")
        self.assertEqual(dub_config["tts"]["voice"], "en-GB-RyanNeural")
        self.assertEqual(dub_config["tts"]["fallback_voices"], ["en-US-JennyNeural"])


if __name__ == "__main__":
    unittest.main()
