import os

from pillow_compat import patch_pillow_resampling_aliases

patch_pillow_resampling_aliases()

from moviepy.config import change_settings
from moviepy.editor import CompositeVideoClip, TextClip, VideoFileClip
from moviepy.video.tools.subtitles import SubtitlesClip

from config import (
    equalize_subtitles,
    get_font,
    get_fonts_dir,
    get_imagemagick_path,
    get_threads,
)
from status import info, warning


change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})


class DubSubtitleRenderer:
    def __init__(self, config: dict) -> None:
        self.config = config

    def burn(self, video_path: str, segments: list[dict], run_dir: str) -> str:
        subtitles_config = self.config.get("subtitles", {})
        if not subtitles_config.get("enabled", True):
            return video_path

        language = str(self.config.get("language", "vi")).strip().lower() or "vi"
        srt_path = os.path.join(run_dir, f"transcript_{language}.srt")
        self._write_srt(srt_path, segments)

        try:
            equalize_subtitles(srt_path, int(subtitles_config.get("max_chars", 12)))
        except Exception as exc:
            warning(f"Could not equalize dub subtitles: {exc}")

        temp_output_path = os.path.join(run_dir, "dubbed_video_subtitled.mp4")
        font_path = os.path.join(get_fonts_dir(), get_font())
        fontsize = int(subtitles_config.get("fontsize", 70))

        def generator(text: str) -> TextClip:
            return TextClip(
                text,
                font=font_path,
                fontsize=fontsize,
                color="#FFFF00",
                stroke_color="gray",
                stroke_width=2,
                size=(900, None),
                method="caption",
            )

        info(f" => Burning {self._language_name()} subtitles into dubbed video...")
        video_clip = VideoFileClip(video_path)
        position_y = self._subtitle_position_y(video_clip.h, subtitles_config)
        subtitles = SubtitlesClip(srt_path, generator).set_position(("center", position_y))
        final_clip = CompositeVideoClip([video_clip, subtitles]).set_duration(video_clip.duration)

        try:
            final_clip.write_videofile(
                temp_output_path,
                codec="libx264",
                audio_codec="aac",
                threads=get_threads(),
            )
        finally:
            final_clip.close()
            video_clip.close()

        os.replace(temp_output_path, video_path)
        return video_path

    def _write_srt(self, srt_path: str, segments: list[dict]) -> None:
        lines = []
        subtitle_index = 1
        for segment in segments:
            text = str(segment.get("text_vi") or segment.get("text") or "").strip()
            if not text:
                continue

            lines.extend(
                [
                    str(subtitle_index),
                    f"{self._srt_time(float(segment['start']))} --> {self._srt_time(float(segment['end']))}",
                    text,
                    "",
                ]
            )
            subtitle_index += 1

        with open(srt_path, "w", encoding="utf-8") as file:
            file.write("\n".join(lines))

    def _language_name(self) -> str:
        language = str(self.config.get("language", "vi")).strip().lower()
        if language.startswith("en"):
            return "English"
        if language.startswith("vi"):
            return "Vietnamese"
        return language or "translated"

    @staticmethod
    def _subtitle_position_y(video_height: int, subtitles_config: dict) -> int:
        configured_position = subtitles_config.get("position_y")
        default_position = int(video_height * 0.78)
        if configured_position in ("", None):
            return default_position

        try:
            position_y = int(configured_position)
        except (TypeError, ValueError):
            return default_position

        min_y = int(video_height * 0.55)
        max_y = int(video_height * 0.86)
        if position_y > max_y or position_y < min_y:
            return default_position

        return position_y

    @staticmethod
    def _srt_time(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
