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

from classes.Runway import Runway


class RunwayTests(unittest.TestCase):
    def test_create_image_to_video_task_returns_id(self) -> None:
        response = Mock()
        response.json.return_value = {"id": "task-123"}
        response.raise_for_status.return_value = None

        with patch("classes.Runway.requests.post", return_value=response) as post_mock:
            task_id = Runway("key").create_image_to_video_task(
                prompt="cinematic EV",
                image_url="https://example.com/image.jpg",
                model="gen4.5",
                duration=5,
                ratio="720:1280",
            )

        self.assertEqual(task_id, "task-123")
        payload = post_mock.call_args.kwargs["json"]
        headers = post_mock.call_args.kwargs["headers"]
        self.assertEqual(payload["promptImage"], "https://example.com/image.jpg")
        self.assertEqual(payload["promptText"], "cinematic EV")
        self.assertEqual(payload["model"], "gen4.5")
        self.assertEqual(payload["duration"], 5)
        self.assertEqual(payload["ratio"], "720:1280")
        self.assertEqual(headers["X-Runway-Version"], "2024-11-06")

    def test_wait_for_task_returns_first_output_url(self) -> None:
        response = Mock()
        response.json.return_value = {
            "status": "SUCCEEDED",
            "output": ["https://example.com/video.mp4"],
        }
        response.raise_for_status.return_value = None

        with patch("classes.Runway.requests.get", return_value=response):
            video_url = Runway("key").wait_for_task(
                task_id="task-123",
                poll_interval_seconds=3,
                timeout_seconds=60,
            )

        self.assertEqual(video_url, "https://example.com/video.mp4")

    def test_download_video_writes_to_mp_folder(self) -> None:
        response = Mock()
        response.content = b"video"
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, ".mp"))

            with patch("classes.Runway.ROOT_DIR", temp_dir):
                with patch("classes.Runway.requests.get", return_value=response):
                    output_path = Runway("key").download_video("https://example.com/video.mp4")

            with open(output_path, "rb") as file:
                content = file.read()

        self.assertEqual(content, b"video")
        self.assertTrue(output_path.endswith("-runway-hook.mp4"))


if __name__ == "__main__":
    unittest.main()
