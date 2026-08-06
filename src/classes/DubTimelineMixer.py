import json
import os
import subprocess

from .DubFfmpeg import resolve_ffmpeg


class DubTimelineMixer:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.ffmpeg = resolve_ffmpeg(config)

    def mix(self, segments: list[dict], background_path: str, run_dir: str) -> str:
        voice_path = os.path.join(run_dir, "voice_vi_full.wav")
        output_path = os.path.join(run_dir, "audio_vi_full.wav")
        timeline_plan = []

        inputs = []
        filters = []
        delayed_labels = []
        for input_index, segment in enumerate(segments):
            inputs.extend(["-i", segment["audio_path"]])
            delay_ms = int(float(segment["start"]) * 1000)
            label = f"v{input_index}"
            filters.append(f"[{input_index}:a]adelay={delay_ms}|{delay_ms}[{label}]")
            delayed_labels.append(f"[{label}]")
            timeline_plan.append(
                {
                    "index": segment["index"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "audio_path": segment["audio_path"],
                }
            )

        if not inputs:
            raise ValueError("No TTS segments to mix")

        filters.append(f"{''.join(delayed_labels)}amix=inputs={len(delayed_labels)}:normalize=0[voice]")
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                *inputs,
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[voice]",
                voice_path,
            ],
            check=True,
        )

        if background_path:
            subprocess.run(
                [
                    self.ffmpeg,
                    "-y",
                    "-i",
                    background_path,
                    "-i",
                    voice_path,
                    "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0[a]",
                    "-map",
                    "[a]",
                    output_path,
                ],
                check=True,
            )
        else:
            os.replace(voice_path, output_path)

        with open(os.path.join(run_dir, "timeline_plan.json"), "w", encoding="utf-8") as file:
            json.dump(timeline_plan, file, ensure_ascii=False, indent=2)

        return output_path
