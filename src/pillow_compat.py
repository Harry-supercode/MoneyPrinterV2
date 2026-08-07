from PIL import Image


def patch_pillow_resampling_aliases() -> None:
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
