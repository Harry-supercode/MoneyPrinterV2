import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from classes.FacebookReels import FacebookReels


class FacebookReelsTests(unittest.TestCase):
    def test_clean_caption_normalizes_whitespace(self) -> None:
        caption = FacebookReels._clean_caption(" Title\n\n  #ev   #finance ")

        self.assertEqual(caption, "Title #ev #finance")

    def test_clean_caption_limits_to_facebook_reel_caption_length(self) -> None:
        caption = FacebookReels._clean_caption("a" * 2100)

        self.assertEqual(len(caption), 2000)


if __name__ == "__main__":
    unittest.main()
