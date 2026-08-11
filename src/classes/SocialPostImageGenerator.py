import base64
import os
from pathlib import Path
from uuid import uuid4

import requests

from config import (
    ROOT_DIR,
    get_nanobanana2_api_base_url,
    get_nanobanana2_api_key,
    get_nanobanana2_aspect_ratio,
    get_nanobanana2_model,
    get_pexels_api_key,
)
from status import info, warning


class SocialPostImageGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.output_root = Path(ROOT_DIR) / str(
            config.get("output_root", "output/social_posts")
        )

    def generate(self, topic: str, text: str) -> str:
        image_config = self.config.get("image_generation", {})
        if not image_config.get("enabled"):
            return ""

        prompt = self._build_prompt(topic, text, image_config)
        provider = str(image_config.get("provider", "nanobanana2")).strip().lower()

        if provider == "pexels":
            return self._generate_pexels(prompt) or self._generate_nanobanana2(prompt) or ""

        return self._generate_nanobanana2(prompt) or self._generate_pexels(prompt) or ""

    def _build_prompt(self, topic: str, text: str, image_config: dict) -> str:
        style = str(
            image_config.get(
                "style",
                "professional Vietnamese technology brand visual, clean modern, trustworthy",
            )
        ).strip()
        return (
            f"Create a social media image for HIEMEE.\n"
            f"Topic: {topic}\n"
            f"Post summary: {text[:500]}\n"
            f"Style: {style}\n"
            "Avoid readable text, logos, fake UI screens, financial promises, and misleading claims."
        )

    def _generate_nanobanana2(self, prompt: str) -> str:
        api_key = get_nanobanana2_api_key()
        if not api_key:
            warning("nanobanana2_api_key/GEMINI_API_KEY is not configured for social post image generation.")
            return ""

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        aspect_ratio = get_nanobanana2_aspect_ratio()
        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        try:
            info(" => Generating social post image with Nano Banana 2...")
            response = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            body = response.json()

            for candidate in body.get("candidates", []):
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not inline_data:
                        continue

                    data = inline_data.get("data")
                    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                    if data and str(mime_type).startswith("image/"):
                        return self._persist_image(base64.b64decode(data), "nanobanana2")

            warning("Nano Banana 2 did not return an image payload for social post.")
            return ""
        except Exception as exc:
            warning(f"Failed to generate social post image with Nano Banana 2: {exc}")
            return ""

    def _generate_pexels(self, prompt: str) -> str:
        api_key = get_pexels_api_key()
        if not api_key:
            warning("pexels_api_key/PEXELS_API_KEY is not configured for social post image generation.")
            return ""

        try:
            info(" => Downloading social post image from Pexels...")
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": api_key},
                params={
                    "query": prompt[:180],
                    "orientation": "portrait",
                    "per_page": 1,
                },
                timeout=60,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if not photos:
                warning("Pexels did not return photos for social post image query.")
                return ""

            photo_url = photos[0]["src"].get("portrait") or photos[0]["src"].get("large")
            if not photo_url:
                warning("Pexels photo response did not include a usable social post image URL.")
                return ""

            image_response = requests.get(photo_url, timeout=60)
            image_response.raise_for_status()
            return self._persist_image(image_response.content, "pexels")
        except Exception as exc:
            warning(f"Failed to download social post image from Pexels: {exc}")
            return ""

    def _persist_image(self, image_bytes: bytes, provider: str) -> str:
        self.output_root.mkdir(parents=True, exist_ok=True)
        image_path = self.output_root / f"{uuid4()}-{provider}.png"
        with image_path.open("wb") as image_file:
            image_file.write(image_bytes)
        return os.path.abspath(image_path)
