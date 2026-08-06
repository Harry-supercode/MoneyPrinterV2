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

import utils


class SongSelectionTests(unittest.TestCase):
    def test_get_audio_files_includes_supported_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            songs_dir = os.path.join(temp_dir, "Songs")
            os.makedirs(songs_dir)
            for filename in ["a.mp3", "b.flac", "c.txt"]:
                open(os.path.join(songs_dir, filename), "w", encoding="utf-8").close()

            songs = utils.get_audio_files(songs_dir)

        self.assertEqual(songs, ["a.mp3", "b.flac"])

    def test_choose_random_song_avoids_last_song_when_possible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            songs_dir = os.path.join(temp_dir, "Songs")
            mp_dir = os.path.join(temp_dir, ".mp")
            os.makedirs(songs_dir)
            os.makedirs(mp_dir)

            for filename in ["a.mp3", "b.mp3"]:
                open(os.path.join(songs_dir, filename), "w", encoding="utf-8").close()

            with open(os.path.join(mp_dir, "song_history.json"), "w", encoding="utf-8") as file:
                json.dump({"last_song": "a.mp3"}, file)

            with patch.object(utils, "ROOT_DIR", temp_dir):
                selected = os.path.basename(utils.choose_random_song())

        self.assertEqual(selected, "b.mp3")


if __name__ == "__main__":
    unittest.main()
