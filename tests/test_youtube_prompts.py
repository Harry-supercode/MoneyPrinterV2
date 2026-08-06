import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

sys.modules.pop("llm_provider", None)
sys.modules.pop("classes.Tts", None)
sys.modules.pop("classes.YouTube", None)
from classes.YouTube import (
    YouTube,
    clean_youtube_metadata_text,
    fallback_image_prompts,
    is_generic_youtube_title,
    parse_image_prompts_response,
    youtube_title_candidates,
)


class YouTubePromptParsingTests(unittest.TestCase):
    def test_parse_clean_json_array(self) -> None:
        prompts = parse_image_prompts_response('["prompt one", "prompt two"]')

        self.assertEqual(prompts, ["prompt one", "prompt two"])

    def test_parse_json_array_wrapped_in_text(self) -> None:
        prompts = parse_image_prompts_response(
            'Here are the prompts: ["moon photo", "spacecraft launch"]'
        )

        self.assertEqual(prompts, ["moon photo", "spacecraft launch"])

    def test_parse_image_prompts_object(self) -> None:
        prompts = parse_image_prompts_response(
            '{"image_prompts": ["ev charging", "finance app"]}'
        )

        self.assertEqual(prompts, ["ev charging", "finance app"])

    def test_fallback_image_prompts_uses_subject(self) -> None:
        prompts = fallback_image_prompts(
            "customer data for hotel revenue",
            "",
            4,
        )

        self.assertEqual(len(prompts), 4)
        self.assertTrue(all("customer data for hotel revenue" in prompt for prompt in prompts))

    def test_clean_youtube_metadata_text_removes_markdown_noise(self) -> None:
        self.assertEqual(
            clean_youtube_metadata_text('```json\n**"Thiết Kế Website Theo Yêu Cầu"**\n```'),
            "Thiết Kế Website Theo Yêu Cầu",
        )

    def test_generic_youtube_title_is_rejected(self) -> None:
        self.assertTrue(is_generic_youtube_title("Khoảnh khắc bất ngờ"))
        self.assertTrue(is_generic_youtube_title("Here is the title for your video"))
        self.assertFalse(
            is_generic_youtube_title("Thiết Kế Website Theo Yêu Cầu Cho Doanh Nghiệp")
        )

    def test_youtube_title_candidates_extracts_title_from_verbose_answer(self) -> None:
        candidates = youtube_title_candidates(
            'Tiêu đề YouTube Shorts chuẩn SEO: "Tối ưu lợi nhuận bằng dữ liệu khách hàng" '
            "Tương tự, tiêu đề này khớp với nội dung video."
        )

        self.assertEqual(candidates[0], "Tối ưu lợi nhuận bằng dữ liệu khách hàng")

    def test_generate_metadata_uses_fallback_after_invalid_title_attempts(self) -> None:
        youtube = object.__new__(YouTube)
        youtube._niche = "Hie-Software"
        youtube._language = "Vietnamese"
        youtube.subject = "dữ liệu khách hàng giúp doanh nghiệp tối ưu vận hành"
        youtube.script = "Dữ liệu khách hàng giúp doanh nghiệp hiểu nhu cầu thật và vận hành tốt hơn."
        youtube.get_videos = lambda: []
        youtube._is_english_mode_enabled = lambda: False

        responses = iter(["Khoảnh khắc bất ngờ"] * 4)
        youtube.generate_response = lambda prompt: next(responses)

        metadata = youtube.generate_metadata()

        self.assertEqual(
            metadata["title"],
            "dữ liệu khách hàng giúp doanh nghiệp tối ưu vận hành",
        )
        self.assertIn("Hie-Software", metadata["description"])

    def test_generate_metadata_retries_generic_title_and_uses_brand_context(self) -> None:
        youtube = object.__new__(YouTube)
        youtube._niche = "Hie-Software"
        youtube._language = "Vietnamese"
        youtube.subject = "nâng cấp website doanh nghiệp chậm và khó quản trị"
        youtube.script = "Website chậm làm khách hàng rời đi. Hie-Software giúp nâng cấp hệ thống."
        youtube.get_videos = lambda: []
        youtube._is_english_mode_enabled = lambda: False

        responses = iter(
            [
                "Khoảnh khắc bất ngờ",
                "Nâng Cấp Website Doanh Nghiệp Để Tăng Tốc Bán Hàng",
                "Website chậm có thể làm mất khách hàng và giảm hiệu quả bán hàng. Hie-Software hỗ trợ nâng cấp website, tối ưu tốc độ, mobile và quản trị. Tìm hiểu thêm tại https://www.hiemee.com/hie-software #HieSoftware #ThietKeWebsite #WebsiteDoanhNghiep",
            ]
        )
        prompts = []

        def fake_generate_response(prompt: str) -> str:
            prompts.append(prompt)
            return next(responses)

        youtube.generate_response = fake_generate_response

        metadata = youtube.generate_metadata()

        self.assertEqual(
            metadata["title"],
            "Nâng Cấp Website Doanh Nghiệp Để Tăng Tốc Bán Hàng",
        )
        self.assertIn("Hie-Software", metadata["description"])
        self.assertTrue(any("Website, App và Phần mềm theo yêu cầu" in prompt for prompt in prompts))

    def test_generate_prompts_uses_fallback_after_invalid_responses(self) -> None:
        youtube = object.__new__(YouTube)
        youtube.subject = "customer data for hotel revenue"
        youtube.script = "Customer data helps hotel teams improve revenue and operations."
        youtube.generate_response = lambda prompt: "not json"

        prompts = youtube.generate_prompts()

        self.assertEqual(len(prompts), 6)
        self.assertTrue(all("customer data for hotel revenue" in prompt for prompt in prompts))
        self.assertEqual(prompts, youtube.image_prompts)

    def test_duplicate_youtube_title_or_content_is_detected(self) -> None:
        youtube = object.__new__(YouTube)
        youtube.subject = "thiết kế website theo yêu cầu cho doanh nghiệp"
        youtube.script = "Hie-Software thiết kế website theo yêu cầu cho doanh nghiệp."
        youtube.get_videos = lambda: [
            {
                "title": "Thiết Kế Website Theo Yêu Cầu Cho Doanh Nghiệp",
                "description": "Website doanh nghiệp tối ưu tốc độ và SEO.",
                "subject": "thiết kế website theo yêu cầu cho doanh nghiệp",
                "script": "Hie-Software thiết kế website theo yêu cầu cho doanh nghiệp.",
            }
        ]

        self.assertTrue(
            youtube._is_duplicate_title_or_content(
                "Thiết kế website theo yêu cầu cho doanh nghiệp"
            )
        )


if __name__ == "__main__":
    unittest.main()
