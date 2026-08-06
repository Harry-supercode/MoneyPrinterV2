import asyncio
import os
import time
import wave
from uuid import uuid4

import edge_tts

from config import get_tts_voice, get_youtube_english_mode_config
from status import warning


class TTS:
    def tts(self, text: str) -> str:
        output_path = os.path.join(".mp", str(uuid4()) + ".mp3")
        self.synthesize(text, output_path)
        return output_path

    def synthesize(self, text: str, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        voices = self._get_voices()
        normalized_text = " ".join(str(text or "").split())
        last_error = None

        if not normalized_text:
            self._write_silence(output_path, 1.0)
            return output_path

        for voice in voices:
            for attempt in range(1, 4):
                try:
                    self._save_edge_audio(normalized_text, output_path, voice)
                    return output_path
                except Exception as exc:
                    last_error = exc
                    warning(f"Edge TTS failed voice={voice} attempt={attempt}: {exc}")
                    self._remove_partial_file(output_path)
                    time.sleep(min(attempt, 3))

        warning(f"Falling back to silent TTS audio: {last_error}")
        self._write_silence(output_path, self._estimate_duration(normalized_text))

        return output_path

    def _save_edge_audio(self, text: str, output_path: str, voice: str) -> None:
        async def _save() -> None:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate="+10%",
                pitch="+0Hz",
            )
            await communicate.save(output_path)

        asyncio.run(_save())

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("Edge TTS wrote an empty audio file")

    def _get_voices(self) -> list[str]:
        english_mode = get_youtube_english_mode_config()
        if english_mode["enabled"]:
            voices = [english_mode["voice"]]
            voices.extend(english_mode["fallback_voices"])
            return list(dict.fromkeys(voices))

        configured_voice = get_tts_voice()
        voices = [configured_voice or "vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"]
        return list(dict.fromkeys(voices))

    def _write_silence(self, output_path: str, duration: float) -> None:
        sample_rate = 44100
        frame_count = int(max(duration, 1.0) * sample_rate)
        with wave.open(output_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count)

    def _estimate_duration(self, text: str) -> float:
        word_count = max(1, len(text.split()))
        return max(3.0, word_count / 2.2)

    def _remove_partial_file(self, output_path: str) -> None:
        try:
            os.remove(output_path)
        except OSError:
            pass
