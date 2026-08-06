import os
import sys
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from classes.Luma import Luma


class LumaTests(unittest.TestCase):
    def test_create_image_to_video_generation_returns_id(self) -> None:
        response = Mock()
        response.json.return_value = {"id": "gen-123"}
        response.raise_for_status.return_value = None

        with patch("classes.Luma.requests.post", return_value=response) as post_mock:
            generation_id = Luma("key").create_image_to_video_generation(
                prompt="cinematic EV",
                image_url="https://example.com/image.jpg",
                model="ray-flash-2",
                duration="5s",
                resolution="720p",
                aspect_ratio="9:16",
            )

        self.assertEqual(generation_id, "gen-123")
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["keyframes"]["frame0"]["url"], "https://example.com/image.jpg")

    def test_download_video_writes_to_mp_folder(self) -> None:
        response = Mock()
        response.content = b"video"
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, ".mp"))

            with patch("classes.Luma.ROOT_DIR", temp_dir):
                with patch("classes.Luma.requests.get", return_value=response):
                    output_path = Luma("key").download_video("https://example.com/video.mp4")

            with open(output_path, "rb") as file:
                content = file.read()

        self.assertEqual(content, b"video")
        self.assertTrue(output_path.endswith("-luma-hook.mp4"))


if __name__ == "__main__":
    unittest.main()
