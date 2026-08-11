import os
import sys
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from classes.SocialPostGenerator import SocialPostGenerator


class SocialPostGeneratorTests(unittest.TestCase):
    def test_appends_configured_footer_after_generated_body(self) -> None:
        generator = SocialPostGenerator(
            {
                "output_root": "output/social_posts",
                "language": "vi",
                "brand_name": "HIEMEE",
                "tone": "concise",
                "max_chars": 50,
                "post_footer": "#Hiemee\nWebsite: https://hiemee.com",
            }
        )

        with patch("classes.SocialPostGenerator.generate_text", return_value="Nội dung chính rất dài để kiểm tra phần body bị cắt."):
            text = generator._generate_text("HieFundi")

        self.assertIn("#Hiemee", text)
        self.assertTrue(text.endswith("Website: https://hiemee.com"))

    def test_does_not_duplicate_footer(self) -> None:
        generator = SocialPostGenerator(
            {
                "output_root": "output/social_posts",
                "language": "vi",
                "brand_name": "HIEMEE",
                "tone": "concise",
                "max_chars": 500,
                "post_footer": "#Hiemee",
            }
        )

        with patch("classes.SocialPostGenerator.generate_text", return_value="Nội dung\n\n#Hiemee"):
            text = generator._generate_text("HieFundi")

        self.assertEqual(text.count("#Hiemee"), 1)

    def test_strips_generated_body_hashtags_and_keeps_footer_hashtags(self) -> None:
        generator = SocialPostGenerator(
            {
                "output_root": "output/social_posts",
                "language": "vi",
                "brand_name": "HIEMEE",
                "tone": "concise",
                "max_chars": 500,
                "post_footer": "#Hiemee #HieFundi",
            }
        )

        with patch(
            "classes.SocialPostGenerator.generate_text",
            return_value="Nội dung chính #SaiHashtag\n\n#AnotherBadTag",
        ):
            text = generator._generate_text("HieFundi")

        self.assertNotIn("#SaiHashtag", text)
        self.assertNotIn("#AnotherBadTag", text)
        self.assertTrue(text.endswith("#Hiemee #HieFundi"))

    def test_strips_generated_footer_and_unexpected_script_fragments(self) -> None:
        generator = SocialPostGenerator(
            {
                "output_root": "output/social_posts",
                "language": "Vietnamese",
                "brand_name": "HIEMEE",
                "tone": "concise",
                "max_chars": 500,
                "post_footer": "#Hiemee",
            }
        )

        with patch(
            "classes.SocialPostGenerator.generate_text",
            return_value=(
                "Hãy phát triểnธุรกิจ với hệ sinh thái HIEMEE.\n\n"
                "Footer: Liên hệ với chúng tôi để biết thêm.\n"
                "Dòng lỗi ธุรกิจ cần bị loại bỏ."
            ),
        ):
            text = generator._generate_text("HIEMEE")

        self.assertNotIn("Footer:", text)
        self.assertNotIn("ธุรกิจ", text)
        self.assertIn("phát triển", text)
        self.assertTrue(text.endswith("#Hiemee"))

    def test_strips_generated_contact_cta_and_unsupported_claims(self) -> None:
        generator = SocialPostGenerator(
            {
                "output_root": "output/social_posts",
                "language": "Vietnamese",
                "brand_name": "HIEMEE",
                "tone": "concise",
                "max_chars": 900,
                "post_footer": "#Hiemee",
            }
        )

        with patch(
            "classes.SocialPostGenerator.generate_text",
            return_value=(
                "Hi mọi người! HIEMEE đang phát triển Map Technology.\n\n"
                "Được hỗ trợ bởi đội ngũ chuyên gia hàng đầu, HIEMEE sẵn sàng hợp tác.\n\n"
                "Hãy liên hệ với chúng tôi để biết..."
            ),
        ):
            text = generator._generate_text("MapTechnology")

        self.assertNotIn("chuyên gia hàng đầu", text)
        self.assertNotIn("Hi mọi người", text)
        self.assertNotIn("Hãy liên hệ", text)
        self.assertTrue(text.endswith("#Hiemee"))


if __name__ == "__main__":
    unittest.main()
