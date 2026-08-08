import os
import random
import zipfile
import requests
import platform
import json

from status import *
from config import *

DEFAULT_SONG_ARCHIVE_URLS = []
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
SONG_HISTORY_FILE = "song_history.json"


def close_running_selenium_instances() -> None:
    """
    Closes any running Selenium instances.

    Returns:
        None
    """
    try:
        info(" => Closing running Selenium instances...")

        # Kill all running Firefox instances
        if platform.system() == "Windows":
            os.system("taskkill /f /im firefox.exe")
        else:
            os.system("pkill firefox")

        success(" => Closed running Selenium instances.")

    except Exception as e:
        error(f"Error occurred while closing running Selenium instances: {str(e)}")


def build_url(youtube_video_id: str) -> str:
    """
    Builds the URL to the YouTube video.

    Args:
        youtube_video_id (str): The YouTube video ID.

    Returns:
        url (str): The URL to the YouTube video.
    """
    return f"https://www.youtube.com/watch?v={youtube_video_id}"


def rem_temp_files() -> None:
    """
    Removes temporary files in the `.mp` directory.

    Returns:
        None
    """
    # Path to the `.mp` directory
    mp_dir = os.path.join(ROOT_DIR, ".mp")

    files = os.listdir(mp_dir)

    for file in files:
        path = os.path.join(mp_dir, file)
        if file.endswith(".json") or not os.path.isfile(path):
            continue
        os.remove(path)


def fetch_songs() -> None:
    """
    Downloads songs into songs/ directory to use with geneated videos.

    Returns:
        None
    """
    try:
        info(f" => Fetching songs...")

        files_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(files_dir):
            os.mkdir(files_dir)
            if get_verbose():
                info(f" => Created directory: {files_dir}")
        else:
            existing_audio_files = [
                name
                for name in os.listdir(files_dir)
                if os.path.isfile(os.path.join(files_dir, name))
                and name.lower().endswith(AUDIO_EXTENSIONS)
            ]
            if len(existing_audio_files) > 0:
                return

        configured_url = get_zip_url().strip()
        download_urls = [configured_url] if configured_url else []
        download_urls.extend(DEFAULT_SONG_ARCHIVE_URLS)

        archive_path = os.path.join(files_dir, "songs.zip")
        downloaded = False

        for download_url in download_urls:
            try:
                response = requests.get(download_url, timeout=60)
                response.raise_for_status()

                with open(archive_path, "wb") as file:
                    file.write(response.content)

                SAFE_EXTENSIONS = AUDIO_EXTENSIONS
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if not basename or not basename.lower().endswith(SAFE_EXTENSIONS):
                            warning(f"Skipping non-audio file in archive: {member}")
                            continue
                        if ".." in member or member.startswith("/"):
                            warning(f"Skipping suspicious path in archive: {member}")
                            continue
                        zf.extract(member, files_dir)

                downloaded = True
                break
            except Exception as err:
                warning(f"Failed to fetch songs from {download_url}: {err}")

        if not downloaded:
            raise RuntimeError(
                "Could not download a valid songs archive from any configured URL"
            )

        # Remove the zip file
        if os.path.exists(archive_path):
            os.remove(archive_path)

        success(" => Downloaded Songs to ../Songs.")

    except Exception as e:
        error(f"Error occurred while fetching songs: {str(e)}")


def get_song_history_path() -> str:
    return os.path.join(ROOT_DIR, ".mp", SONG_HISTORY_FILE)


def get_audio_files(songs_dir: str) -> list[str]:
    return sorted(
        name
        for name in os.listdir(songs_dir)
        if os.path.isfile(os.path.join(songs_dir, name))
        and name.lower().endswith(AUDIO_EXTENSIONS)
    )


def get_last_chosen_song() -> str:
    history_path = get_song_history_path()
    if not os.path.exists(history_path):
        return ""

    try:
        with open(history_path, "r", encoding="utf-8") as file:
            return str(json.load(file).get("last_song", ""))
    except Exception:
        return ""


def save_last_chosen_song(song: str) -> None:
    history_path = get_song_history_path()
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    with open(history_path, "w", encoding="utf-8") as file:
        json.dump({"last_song": song}, file, indent=2)


def choose_random_song() -> str:
    """
    Chooses a random song from the songs/ directory.

    Returns:
        str: The path to the chosen song.
    """
    try:
        songs_dir = os.path.join(ROOT_DIR, "Songs")
        songs = get_audio_files(songs_dir)
        if len(songs) == 0:
            raise RuntimeError("No audio files found in Songs directory")

        last_song = get_last_chosen_song()
        choices = [song for song in songs if song != last_song]
        if len(choices) == 0:
            choices = songs

        song = random.choice(choices)
        save_last_chosen_song(song)

        success(f" => Chose song: {song} ({len(songs)} available)")
        return os.path.join(ROOT_DIR, "Songs", song)
    except Exception as e:
        error(f"Error occurred while choosing random song: {str(e)}")
        raise
