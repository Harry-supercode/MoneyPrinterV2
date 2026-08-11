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


if __name__ == "__main__":
    unittest.main()
