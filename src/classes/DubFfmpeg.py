import shutil


def resolve_ffmpeg(config: dict) -> str:
    ffmpeg_path = str(config.get("ffmpeg_path", "ffmpeg")).strip() or "ffmpeg"
    if "/" in ffmpeg_path:
        return ffmpeg_path

    resolved = shutil.which(ffmpeg_path)
    return resolved or ffmpeg_path


def resolve_ffprobe(config: dict) -> str:
    configured = str(config.get("ffprobe_path", "")).strip()
    if configured:
        if "/" in configured:
            return configured
        resolved = shutil.which(configured)
        if resolved:
            return resolved

    ffmpeg_path = resolve_ffmpeg(config)
    if "/" in ffmpeg_path:
        candidate = ffmpeg_path.replace("ffmpeg", "ffprobe")
        if shutil.which(candidate) or candidate:
            return candidate

    return shutil.which("ffprobe") or "ffprobe"
