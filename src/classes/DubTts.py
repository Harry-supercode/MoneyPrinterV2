import asyncio
import math
import os
import subprocess

import edge_tts

from status import warning
from .DubFfmpeg import resolve_ffmpeg, resolve_ffprobe


class DubTts:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.ffmpeg = resolve_ffmpeg(config)
        self.ffprobe = resolve_ffprobe(config)

    def synthesize_segments(self, segments: list[dict], run_dir: str) -> list[dict]:
        segments_dir = os.path.join(run_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)

        rendered_segments = []
        for segment in segments:
            duration = max(0.1, float(segment["end"]) - float(segment["start"]))
            output_path = os.path.join(segments_dir, f"seg_{int(segment['index']):03}.wav")
            render_result = self._render_segment_voice(segment, output_path, duration)
            rendered_segments.append({**segment, **render_result, "audio_path": output_path})

        return rendered_segments

    def _render_segment_voice(self, segment: dict, output_path: str, duration: float) -> dict:
        provider = self.config.get("tts", {}).get("provider", "edge")
        if provider == "edge":
            return self._render_edge_voice(segment, output_path, duration)

        if provider in {"lucylab", "vivibe"}:
            raise NotImplementedError(
                f"Dub TTS provider '{provider}' needs its API endpoint/payload docs before wiring."
            )

        return self._render_placeholder_voice(output_path, duration)

    def _render_edge_voice(self, segment: dict, output_path: str, target_duration: float) -> dict:
        text = str(segment.get("text_vi") or segment.get("text") or "").strip()
        if not text:
            self._render_silence(output_path, target_duration)
            return {"tts_provider": "silence", "tts_speed": 1.0}

        raw_path = output_path.replace(".wav", ".raw.mp3")
        tts_config = self.config.get("tts", {})
        voice = tts_config.get("voice", "vi-VN-NamMinhNeural")
        voices = [voice]
        for fallback_voice in tts_config.get("fallback_voices", []):
            if fallback_voice not in voices:
                voices.append(fallback_voice)

        last_error = None
        for candidate_voice in voices:
            for attempt in range(1, 4):
                try:
                    self._save_edge_audio(text, raw_path, candidate_voice)
                    raw_duration = self._probe_duration(raw_path)
                    max_speed = float(tts_config.get("max_speed", 1.3))
                    speed = 1.0
                    if raw_duration > target_duration:
                        speed = min(raw_duration / target_duration, max_speed)

                    self._convert_audio(raw_path, output_path, speed)

                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass

                    return {
                        "tts_provider": "edge",
                        "tts_voice": candidate_voice,
                        "tts_speed": round(speed, 3),
                        "tts_raw_duration": round(raw_duration, 3),
                        "tts_target_duration": round(target_duration, 3),
                    }
                except Exception as exc:
                    last_error = exc
                    warning(
                        "Edge TTS failed for "
                        f"seg_{int(segment['index']):03} voice={candidate_voice} "
                        f"attempt={attempt}: {exc}"
                    )
                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass

        fallback_provider = tts_config.get("fallback_provider", "placeholder")
        warning(
            f"Falling back to {fallback_provider} audio for "
            f"seg_{int(segment['index']):03}: {last_error}"
        )
        if fallback_provider == "silence":
            self._render_silence(output_path, target_duration)
            return {"tts_provider": "silence", "tts_speed": 1.0, "tts_error": str(last_error)}

        result = self._render_placeholder_voice(output_path, target_duration)
        return {**result, "tts_error": str(last_error)}

    def _save_edge_audio(self, text: str, raw_path: str, voice: str) -> None:
        normalized_text = " ".join(text.split())

        async def _save() -> None:
            communicate = edge_tts.Communicate(
                text=normalized_text,
                voice=voice,
                rate="+0%",
                pitch="+0Hz",
            )
            await communicate.save(raw_path)

        asyncio.run(_save())

    def _render_placeholder_voice(self, output_path: str, duration: float) -> None:
        frequency = 440
        clamped_duration = str(max(0.1, math.ceil(duration * 100) / 100))
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration={clamped_duration}",
                "-ar",
                "44100",
                "-ac",
                "1",
                output_path,
            ],
            check=True,
        )
        return {"tts_provider": "placeholder", "tts_speed": 1.0}

    def _render_silence(self, output_path: str, duration: float) -> None:
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=mono:sample_rate=44100:duration={duration}",
                output_path,
            ],
            check=True,
        )

    def _convert_audio(self, input_path: str, output_path: str, speed: float) -> None:
        command = [self.ffmpeg, "-y", "-i", input_path]
        if speed > 1.01:
            command.extend(["-filter:a", f"atempo={speed:.3f}"])
        command.extend(["-ar", "44100", "-ac", "1", output_path])
        subprocess.run(command, check=True)

    def _probe_duration(self, audio_path: str) -> float:
        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
