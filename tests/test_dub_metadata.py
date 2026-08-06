import os
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

sys.modules.pop("llm_provider", None)
sys.modules.pop("classes.DubMetadata", None)
sys.modules.pop("classes.DubUploadAdapter", None)
from classes.DubMetadata import DubMetadata
from classes.DubUploadAdapter import DubUploadAdapter


class DubMetadataTests(unittest.TestCase):
    def test_english_chinese_source_uses_specific_heuristic_title(self) -> None:
        metadata = DubMetadata({"language": "en"})

        title = metadata._content_fallback_title("雨天小狗路滑", "", "")

        self.assertEqual(title, "A Dog's Slippery Rainy-Day Adventure")

    def test_english_fallback_uses_transcript_when_source_is_unknown_chinese(self) -> None:
        metadata = DubMetadata({"language": "en"})

        title = metadata._content_fallback_title(
            "这是一个没有已知关键词的视频",
            "A chef prepares handmade noodles for the dinner rush.",
            "",
        )

        self.assertEqual(
            title,
            "A chef prepares handmade noodles for the dinner rush",
        )

    def test_generic_english_title_is_rejected(self) -> None:
        self.assertTrue(DubMetadata._is_generic_title("A viral short dubbed in English"))
        self.assertTrue(
            DubMetadata._is_generic_title("Viral short dubbed in English: trending video")
        )
        self.assertTrue(DubMetadata._is_generic_title("A funny video worth watching"))
        self.assertTrue(DubMetadata._is_generic_title("You won't believe this moment"))

    def test_generic_vietnamese_title_is_rejected(self) -> None:
        self.assertTrue(DubMetadata._is_generic_title("Khoảnh khắc bất ngờ trong video này"))
        self.assertTrue(DubMetadata._is_generic_title("Một video hài hước đáng xem"))
        self.assertFalse(DubMetadata._is_generic_title("Chú chó trượt ngã trong ngày mưa"))

    def test_llm_failure_is_logged_and_content_fallback_survives(self) -> None:
        metadata = DubMetadata({"language": "en"})

        with (
            patch("classes.DubMetadata.get_active_model", return_value="test-model"),
            patch("classes.DubMetadata.generate_text", side_effect=RuntimeError("offline")),
            patch("classes.DubMetadata.warning") as warning_mock,
        ):
            title = metadata._title_from_llm("A source title", "A transcript", "keyword", "English")

        self.assertEqual(title, "")
        warning_mock.assert_called_once()

    def test_english_caption_no_longer_uses_old_fixed_spam_hashtags(self) -> None:
        metadata_builder = DubMetadata({"language": "en"})
        metadata = {
            "title": "A Dog Waits Patiently for Dinner",
            "description": (
                "A Dog Waits Patiently for Dinner\n\n"
                "A dog waits beside the kitchen while dinner is being prepared."
            ),
            "hashtags": metadata_builder._content_hashtags(
                "A Dog Waits Patiently for Dinner",
                "A dog waits beside the kitchen while dinner is being prepared.",
                "dog dinner",
            ),
        }

        caption = metadata_builder._caption(metadata)

        self.assertNotIn("#review", caption.lower())
        self.assertNotIn("#englishdub", caption.lower())
        self.assertNotIn("#viral", caption.lower())
        self.assertIn("dog waits beside the kitchen", caption)

    def test_caption_fallback_does_not_use_chinese_source_title(self) -> None:
        metadata_builder = DubMetadata({"language": "vi"})
        metadata = {
            "title": "Chú chó trượt ngã trong ngày mưa",
            "description": "",
            "hashtags": ["#Shorts"],
            "source_title": "雨天小狗路滑",
            "keyword": "雨天小狗路滑",
        }

        caption = metadata_builder._caption(metadata)

        self.assertNotRegex(caption, r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
        self.assertEqual(caption, "Chú chó trượt ngã trong ngày mưa\n\n#Shorts")

    def test_generate_filters_chinese_description_and_hashtags(self) -> None:
        with tempfile.TemporaryDirectory() as run_dir:
            with open(os.path.join(run_dir, "source_metadata.json"), "w", encoding="utf-8") as file:
                file.write('{"source_title": "雨天小狗路滑"}')

            with (
                patch("classes.DubMetadata.get_active_model", return_value="test-model"),
                patch(
                    "classes.DubMetadata.generate_text",
                    return_value=(
                        '{"title":"Chú chó trượt ngã trong ngày mưa",'
                        '"description":"雨天小狗路滑\\nMột khoảnh khắc hài hước trong ngày mưa.",'
                        '"hashtags":["#Shorts","#小狗","#ChoCung"]}'
                    ),
                ),
            ):
                metadata = DubMetadata({"language": "vi"}).generate(
                    {"keyword": "雨天小狗路滑"},
                    [{"text_vi": "Chú chó chạy trên nền đường trơn và bị trượt ngã."}],
                    run_dir,
                )

        self.assertNotRegex(metadata["title"], r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
        self.assertNotRegex(metadata["description"], r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
        self.assertNotIn("#小狗", metadata["hashtags"])


class DubUploadAdapterTitleTests(unittest.TestCase):
    def test_duplicate_title_comparison_ignores_case_and_punctuation(self) -> None:
        account = {
            "videos": [
                {"title": "A Dog's Slippery Rainy-Day Adventure"},
            ]
        }

        self.assertTrue(
            DubUploadAdapter._is_duplicate_youtube_title(
                account,
                "a dogs slippery rainy day adventure",
            )
        )

    def test_distinct_title_is_allowed(self) -> None:
        account = {"videos": [{"title": "A Cat Learns to Open the Door"}]}

        self.assertFalse(
            DubUploadAdapter._is_duplicate_youtube_title(
                account,
                "A Dog Waits Patiently for Dinner",
            )
        )

    def test_youtube_upload_refuses_generic_title_before_browser_start(self) -> None:
        adapter = DubUploadAdapter({"upload": {"youtube": True}})

        result = adapter._upload_youtube(
            {"videos": []},
            "/tmp/video.mp4",
            {"title": "A viral short dubbed in English"},
        )

        self.assertFalse(result["success"])
        self.assertIn("generic", result["error"])

    def test_youtube_upload_refuses_title_already_in_account_cache(self) -> None:
        title = "A Dog Waits Patiently for Dinner"
        adapter = DubUploadAdapter({"upload": {"youtube": True}})

        result = adapter._upload_youtube(
            {"videos": [{"title": title}]},
            "/tmp/video.mp4",
            {"title": title},
        )

        self.assertFalse(result["success"])
        self.assertIn("duplicate", result["error"])

    def test_youtube_upload_refuses_chinese_description_before_browser_start(self) -> None:
        adapter = DubUploadAdapter({"upload": {"youtube": True}})

        result = adapter._upload_youtube(
            {"videos": []},
            "/tmp/video.mp4",
            {
                "title": "Chú chó trượt ngã trong ngày mưa",
                "description": "雨天小狗路滑",
            },
        )

        self.assertFalse(result["success"])
        self.assertIn("Chinese text", result["error"])

    def test_tiktok_upload_refuses_chinese_caption_before_browser_start(self) -> None:
        adapter = DubUploadAdapter({"upload": {"tiktok": True}})

        result = adapter._upload_tiktok(
            {"firefox_profile": "/tmp/profile"},
            "/tmp/video.mp4",
            "Chú chó trượt ngã\n\n雨天小狗路滑",
        )

        self.assertFalse(result["success"])
        self.assertIn("Chinese text", result["error"])


if __name__ == "__main__":
    unittest.main()
