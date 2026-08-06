import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auto_hashtag import build_caption


class AutoHashtagTests(unittest.TestCase):
    def test_build_caption_uses_limited_hiemee_brand_hashtags(self) -> None:
        caption = build_caption(
            "HIEMEE builds software for hospitality and real estate",
            "A founder journey from cashflow to assets.",
        )

        hashtags = [word for word in caption.split() if word.startswith("#")]

        self.assertLessEqual(len(hashtags), 4)
        self.assertIn("#Hiemee", hashtags)
        self.assertIn("#HiemeeGround", hashtags)


if __name__ == "__main__":
    unittest.main()
