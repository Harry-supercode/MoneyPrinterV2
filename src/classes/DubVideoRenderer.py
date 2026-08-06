import os
import subprocess

from .DubFfmpeg import resolve_ffmpeg


class DubVideoRenderer:
    def __init__(self, config: dict) -> None:
        self.ffmpeg = resolve_ffmpeg(config)

    def render(self, source_video_path: str, audio_path: str, run_dir: str) -> str:
        output_path = os.path.join(run_dir, "dubbed_video.mp4")
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                source_video_path,
                "-i",
                audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                output_path,
            ],
            check=True,
        )
        return output_path
