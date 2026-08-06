import json
import os
import subprocess

from config import get_whisper_compute_type, get_whisper_device, get_whisper_model
from status import info, warning
from .DubFfmpeg import resolve_ffmpeg, resolve_ffprobe


class DubAsr:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.ffmpeg = resolve_ffmpeg(config)
        self.ffprobe = resolve_ffprobe(config)

    def transcribe(self, audio_path: str, run_dir: str) -> list[dict]:
        transcript_path = self.config.get("transcript_path", "")
        if not transcript_path:
            segments = self._transcribe_local_whisper(audio_path)
            if not segments:
                segments = self._fallback_segments(audio_path, run_dir)
            self._write_json(run_dir, segments)
            self._write_srt(run_dir, segments)
            return segments

        if not os.path.exists(transcript_path):
            raise FileNotFoundError(f"dub_pipeline.transcript_path not found: {transcript_path}")

        with open(transcript_path, "r", encoding="utf-8") as file:
            raw_segments = json.load(file)

        segments = self._normalize_segments(raw_segments)
        self._write_json(run_dir, segments)
        self._write_srt(run_dir, segments)
        return segments

    def _transcribe_local_whisper(self, audio_path: str) -> list[dict]:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is required when dub_pipeline.transcript_path is empty"
            )

        info(
            " => Running local Whisper ASR "
            f"model={get_whisper_model()} device={get_whisper_device()}"
        )
        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        whisper_segments, _ = model.transcribe(audio_path, vad_filter=True)

        segments = []
        for idx, segment in enumerate(whisper_segments, start=1):
            text = str(segment.text).strip()
            if not text:
                continue

            segments.append(
                {
                    "index": idx,
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                }
            )

        return segments

    def _fallback_segments(self, audio_path: str, run_dir: str) -> list[dict]:
        fallback_text = str(
            self.config.get("fallback_transcript_text", "Xem hết video này nhé.")
        ).strip()
        if not fallback_text:
            raise RuntimeError("Local Whisper did not return any transcript segments")

        duration = max(1.0, self._probe_duration(audio_path))
        start = 0.3 if duration > 1.5 else 0.0
        end = max(start + 0.8, min(duration - 0.2, duration))
        warning(
            "Local Whisper did not return transcript segments; "
            "using configured fallback transcript text."
        )

        metadata_path = os.path.join(run_dir, "asr_fallback.json")
        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "reason": "local_whisper_empty",
                    "audio_path": audio_path,
                    "duration": round(duration, 3),
                    "fallback_text": fallback_text,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )

        return [
            {
                "index": 1,
                "start": start,
                "end": end,
                "text": fallback_text,
                "text_vi": fallback_text,
                "asr_fallback": True,
            }
        ]

    def _probe_duration(self, audio_path: str) -> float:
        try:
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
        except Exception:
            return 1.0

    def _normalize_segments(self, raw_segments: list[dict]) -> list[dict]:
        segments = []
        for idx, segment in enumerate(raw_segments, start=1):
            segments.append(
                {
                    "index": int(segment.get("index", idx)),
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "text": str(segment.get("text", "")).strip(),
                }
            )
        return segments

    def _write_json(self, run_dir: str, segments: list[dict]) -> None:
        with open(os.path.join(run_dir, "transcript_original.json"), "w", encoding="utf-8") as file:
            json.dump(segments, file, ensure_ascii=False, indent=2)

    def _write_srt(self, run_dir: str, segments: list[dict]) -> None:
        lines = []
        for segment in segments:
            lines.extend(
                [
                    str(segment["index"]),
                    f"{self._srt_time(segment['start'])} --> {self._srt_time(segment['end'])}",
                    segment["text"],
                    "",
                ]
            )

        with open(os.path.join(run_dir, "transcript_original.srt"), "w", encoding="utf-8") as file:
            file.write("\n".join(lines))

    @staticmethod
    def _srt_time(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
