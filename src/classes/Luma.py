import os
import time
from uuid import uuid4

import requests
from requests import HTTPError

from config import ROOT_DIR
from status import info, warning


LUMA_GENERATIONS_URL = "https://api.lumalabs.ai/dream-machine/v1/generations"


class Luma:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Luma API key is not configured.")

        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

    def create_image_to_video_generation(
        self,
        prompt: str,
        image_url: str,
        model: str,
        duration: str,
        resolution: str,
        aspect_ratio: str,
    ) -> str:
        payload = {
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "keyframes": {
                "frame0": {
                    "type": "image",
                    "url": image_url,
                }
            },
        }

        response = requests.post(
            LUMA_GENERATIONS_URL,
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        generation_id = response.json().get("id")
        if not generation_id:
            raise RuntimeError(f"Luma did not return a generation id: {response.text}")

        info(f" => Created Luma generation: {generation_id}")
        return generation_id

    def wait_for_generation(
        self,
        generation_id: str,
        poll_interval_seconds: int,
        timeout_seconds: int,
    ) -> str:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = requests.get(
                f"{LUMA_GENERATIONS_URL}/{generation_id}",
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()
            body = response.json()
            state = body.get("state")

            if state == "completed":
                video_url = body.get("assets", {}).get("video")
                if not video_url:
                    raise RuntimeError(f"Luma completed without a video asset: {body}")

                return video_url

            if state == "failed":
                failure_reason = body.get("failure_reason") or "unknown reason"
                raise RuntimeError(f"Luma generation failed: {failure_reason}")

            info(f" => Waiting for Luma generation {generation_id}: {state}")
            time.sleep(poll_interval_seconds)

        raise TimeoutError(f"Luma generation timed out after {timeout_seconds}s.")

    def download_video(self, video_url: str) -> str:
        output_path = os.path.join(ROOT_DIR, ".mp", f"{uuid4()}-luma-hook.mp4")

        response = requests.get(video_url, timeout=300)
        response.raise_for_status()

        with open(output_path, "wb") as file:
            file.write(response.content)

        info(f' => Downloaded Luma hook video to "{output_path}"')
        return output_path

    def generate_hook_video(
        self,
        prompt: str,
        image_url: str,
        model: str,
        duration: str,
        resolution: str,
        aspect_ratio: str,
        poll_interval_seconds: int,
        timeout_seconds: int,
    ) -> str:
        if not image_url.startswith("http"):
            raise ValueError("Luma image-to-video requires a public image URL.")

        try:
            generation_id = self.create_image_to_video_generation(
                prompt=prompt,
                image_url=image_url,
                model=model,
                duration=duration,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
            )
            video_url = self.wait_for_generation(
                generation_id=generation_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
            )
            return self.download_video(video_url)
        except HTTPError as exc:
            response = exc.response
            detail = response.text if response is not None else str(exc)
            status_code = response.status_code if response is not None else "unknown"
            warning(f"Luma hook generation failed with HTTP {status_code}: {detail}")
            return None
        except Exception as exc:
            warning(f"Luma hook generation failed: {exc}")
            return None
