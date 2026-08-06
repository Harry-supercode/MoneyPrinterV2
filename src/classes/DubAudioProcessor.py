import os
import subprocess

from status import warning
from .DubFfmpeg import resolve_ffmpeg, resolve_ffprobe


class DubAudioProcessor:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.ffmpeg = resolve_ffmpeg(config)
        self.ffprobe = resolve_ffprobe(config)

    def extract_audio(self, source_video_path: str, run_dir: str) -> str:
        output_path = os.path.join(run_dir, "original_audio.wav")
        if not self._has_audio_stream(source_video_path):
            warning(
                "Source video has no audio stream; generating silent original audio."
            )
            duration = max(0.1, self._probe_duration(source_video_path))
            self._render_silence_audio(output_path, duration)
            return output_path

        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                source_video_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                output_path,
            ],
            check=True,
        )
        return output_path

    def _has_audio_stream(self, source_video_path: str) -> bool:
        try:
            result = subprocess.run(
                [
                    self.ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "csv=p=0",
                    source_video_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _probe_duration(self, source_video_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    self.ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nokey=1:noprint_wrappers=1",
                    source_video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip() or 0.0)
        except Exception:
            return 0.0

    def _render_silence_audio(self, output_path: str, duration: float) -> None:
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=mono:sample_rate=44100:duration={duration}",
                "-ac",
                "1",
                "-ar",
                "44100",
                output_path,
            ],
            check=True,
        )

    def prepare_background(
        self,
        original_audio_path: str,
        run_dir: str,
        speech_segments: list[dict] | None = None,
    ) -> str:
        mode = self.config.get("background_mode", "duck")
        output_path = os.path.join(run_dir, "background.wav")

        if mode == "none":
            return ""

        if mode != "duck":
            raise NotImplementedError(
                f"Background mode '{mode}' is not implemented. Use 'duck' or 'none'."
            )

        volume = float(self.config.get("background_volume", 0.12))
        speech_duck_volume = float(self.config.get("speech_duck_volume", 0.03))
        filter_audio = self._build_duck_filter(volume, speech_duck_volume, speech_segments or [])
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                original_audio_path,
                "-filter:a",
                filter_audio,
                output_path,
            ],
            check=True,
        )
        return output_path

    @staticmethod
    def _build_duck_filter(
        background_volume: float,
        speech_duck_volume: float,
        speech_segments: list[dict],
    ) -> str:
        background_volume = max(0.0, min(background_volume, 1.0))
        speech_duck_volume = max(0.0, min(speech_duck_volume, 1.0))
        filters = [f"volume={background_volume:.4f}"]

        if not speech_segments or background_volume <= 0:
            return ",".join(filters)

        duck_multiplier = min(speech_duck_volume / background_volume, 1.0)
        for segment in speech_segments:
            start = max(0.0, float(segment.get("start", 0.0)) - 0.08)
            end = max(start + 0.05, float(segment.get("end", start)) + 0.08)
            filters.append(
                f"volume={duck_multiplier:.4f}:enable='between(t,{start:.3f},{end:.3f})'"
            )

        return ",".join(filters)
