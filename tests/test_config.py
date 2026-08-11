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


class PostBridgeConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_platforms_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {"post_bridge": {"enabled": True}})

            with patch.object(config, "ROOT_DIR", temp_dir):
                post_bridge_config = config.get_post_bridge_config()

        self.assertEqual(post_bridge_config["platforms"], ["tiktok", "instagram"])

    def test_invalid_or_empty_platforms_do_not_expand_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "post_bridge": {
                        "enabled": True,
                        "platforms": ["youtube", "tik-tok"],
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                post_bridge_config = config.get_post_bridge_config()

        self.assertEqual(post_bridge_config["platforms"], [])

    def test_non_list_platforms_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "post_bridge": {
                        "enabled": True,
                        "platforms": "tiktok",
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                post_bridge_config = config.get_post_bridge_config()

        self.assertEqual(post_bridge_config["platforms"], [])

    def test_non_object_post_bridge_config_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "post_bridge": None,
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                post_bridge_config = config.get_post_bridge_config()

        self.assertEqual(post_bridge_config["platforms"], ["tiktok", "instagram"])
        self.assertEqual(post_bridge_config["account_ids"], [])
        self.assertFalse(post_bridge_config["enabled"])


class YouTubeTrendsConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_youtube_trends_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                trends_config = config.get_youtube_trends_config()

        self.assertFalse(trends_config["enabled"])
        self.assertEqual(trends_config["source"], "google_trending_rss")
        self.assertEqual(trends_config["geo"], "VN")
        self.assertEqual(trends_config["hl"], "vi")

    def test_youtube_trends_normalizes_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "youtube_trends": {
                        "enabled": True,
                        "source": "google_trending_rss",
                        "geo": "us",
                        "hl": "en-US",
                        "category_filter": " EV ",
                        "max_items": "100",
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                trends_config = config.get_youtube_trends_config()

        self.assertTrue(trends_config["enabled"])
        self.assertEqual(trends_config["geo"], "US")
        self.assertEqual(trends_config["category_filter"], "EV")
        self.assertEqual(trends_config["max_items"], 25)


class YouTubeBrandTopicsConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_youtube_brand_topics_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                brand_topics_config = config.get_youtube_brand_topics_config()

        self.assertFalse(brand_topics_config["enabled"])
        self.assertIn("HIEMEE business ecosystem", brand_topics_config["keywords"])

    def test_youtube_brand_topics_normalizes_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "youtube_brand_topics": {
                        "enabled": True,
                        "keywords": [" Hie-Palace ", "", "HieRealty"],
                        "concepts": [" Cashflow -> Technology -> Assets ", ""],
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                brand_topics_config = config.get_youtube_brand_topics_config()

        self.assertTrue(brand_topics_config["enabled"])
        self.assertEqual(brand_topics_config["keywords"], ["Hie-Palace", "HieRealty"])
        self.assertEqual(
            brand_topics_config["concepts"],
            ["Cashflow -> Technology -> Assets"],
        )


class SocialPostsConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_social_posts_uses_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                social_posts = config.get_social_posts_config()

        self.assertFalse(social_posts["enabled"])
        self.assertFalse(social_posts["automation_verified"])
        self.assertEqual(social_posts["platforms"]["facebook"]["create_url"], "https://www.facebook.com/")
        self.assertFalse(social_posts["platforms"]["youtube"]["enabled"])
        self.assertIn("#Hiemee #HieFundi", social_posts["post_footer"])
        self.assertFalse(social_posts["image_generation"]["enabled"])

    def test_social_posts_normalizes_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "social_posts": {
                        "enabled": True,
                        "automation_verified": True,
                        "browser_profile": " /profiles/social ",
                        "max_chars": "9999",
                        "topics": [" HIEMEE ", ""],
                        "image_paths": [" assets/post.png ", ""],
                        "image_generation": {
                            "enabled": True,
                            "provider": " pexels ",
                            "style": " clean ",
                        },
                        "post_footer": " Footer text ",
                        "platforms": {
                            "facebook": {
                                "enabled": True,
                                "create_url": " https://facebook.com/example ",
                                "post_wait_seconds": "1",
                            },
                            "youtube": {
                                "enabled": True,
                                "create_url": " https://youtube.com/example ",
                                "post_wait_seconds": "999",
                            },
                        },
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                social_posts = config.get_social_posts_config()

        self.assertTrue(social_posts["enabled"])
        self.assertTrue(social_posts["automation_verified"])
        self.assertEqual(social_posts["browser_profile"], "/profiles/social")
        self.assertEqual(social_posts["max_chars"], 2000)
        self.assertEqual(social_posts["topics"], ["HIEMEE"])
        self.assertEqual(social_posts["image_paths"], ["assets/post.png"])
        self.assertTrue(social_posts["image_generation"]["enabled"])
        self.assertEqual(social_posts["image_generation"]["provider"], "pexels")
        self.assertEqual(social_posts["image_generation"]["style"], "clean")
        self.assertEqual(social_posts["post_footer"], "Footer text")
        self.assertEqual(social_posts["platforms"]["facebook"]["post_wait_seconds"], 3)
        self.assertEqual(social_posts["platforms"]["youtube"]["post_wait_seconds"], 120)


class YouTubeEnglishModeConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_youtube_english_mode_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                english_mode = config.get_youtube_english_mode_config()

        self.assertFalse(english_mode["enabled"])
        self.assertEqual(english_mode["language"], "English")
        self.assertEqual(english_mode["voice"], "en-US-GuyNeural")
        self.assertEqual(english_mode["fallback_voices"], ["en-US-JennyNeural"])

    def test_youtube_english_mode_normalizes_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "youtube_english_mode": {
                        "enabled": True,
                        "language": " English ",
                        "voice": " en-GB-RyanNeural ",
                        "fallback_voices": [" en-US-JennyNeural ", "", "en-US-AriaNeural"],
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                english_mode = config.get_youtube_english_mode_config()

        self.assertTrue(english_mode["enabled"])
        self.assertEqual(english_mode["language"], "English")
        self.assertEqual(english_mode["voice"], "en-GB-RyanNeural")
        self.assertEqual(
            english_mode["fallback_voices"],
            ["en-US-JennyNeural", "en-US-AriaNeural"],
        )


class AIVideoConfigTests(unittest.TestCase):
    def write_config(self, directory: str, payload: dict) -> None:
        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_missing_ai_video_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(temp_dir, {})

            with patch.object(config, "ROOT_DIR", temp_dir):
                ai_video_config = config.get_ai_video_config()

        self.assertFalse(ai_video_config["enabled"])
        self.assertEqual(ai_video_config["provider"], "runway")
        self.assertEqual(ai_video_config["mode"], "hook_only")
        self.assertEqual(ai_video_config["model"], "gen4.5")
        self.assertEqual(ai_video_config["duration"], "5")
        self.assertEqual(ai_video_config["ratio"], "720:1280")

    def test_ai_video_normalizes_timeout_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "ai_video": {
                        "enabled": True,
                        "poll_interval_seconds": "1",
                        "timeout_seconds": "10",
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                ai_video_config = config.get_ai_video_config()

        self.assertTrue(ai_video_config["enabled"])
        self.assertEqual(ai_video_config["poll_interval_seconds"], 3)
        self.assertEqual(ai_video_config["timeout_seconds"], 60)

    def test_luma_ai_video_uses_luma_defaults_when_model_is_runway_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.write_config(
                temp_dir,
                {
                    "ai_video": {
                        "enabled": True,
                        "provider": "luma",
                        "model": "gen4.5",
                        "duration": "5",
                    }
                },
            )

            with patch.object(config, "ROOT_DIR", temp_dir):
                ai_video_config = config.get_ai_video_config()

        self.assertTrue(ai_video_config["enabled"])
        self.assertEqual(ai_video_config["provider"], "luma")
        self.assertEqual(ai_video_config["model"], "ray-2")
        self.assertEqual(ai_video_config["duration"], "5s")


if __name__ == "__main__":
    unittest.main()
