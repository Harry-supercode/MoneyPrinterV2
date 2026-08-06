import os
import time
from uuid import uuid4

import requests
from requests import HTTPError

from config import ROOT_DIR
from status import info, warning


RUNWAY_API_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"


class Runway:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Runway API key is not configured.")

        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": RUNWAY_API_VERSION,
        }

    def create_image_to_video_task(
        self,
        prompt: str,
        image_url: str,
        model: str,
        duration: int,
        ratio: str,
    ) -> str:
        payload = {
            "model": model,
            "promptText": prompt,
            "promptImage": image_url,
            "ratio": ratio,
            "duration": duration,
        }

        response = requests.post(
            f"{RUNWAY_API_URL}/image_to_video",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        task_id = response.json().get("id")
        if not task_id:
            raise RuntimeError(f"Runway did not return a task id: {response.text}")

        info(f" => Created Runway image-to-video task: {task_id}")
        return task_id

    def wait_for_task(
        self,
        task_id: str,
        poll_interval_seconds: int,
        timeout_seconds: int,
    ) -> str:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = requests.get(
                f"{RUNWAY_API_URL}/tasks/{task_id}",
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()
            body = response.json()
            status = str(body.get("status", "")).lower()

            if status in ["succeeded", "completed"]:
                output = body.get("output") or []
                if not output:
                    raise RuntimeError(f"Runway completed without a video output: {body}")

                return output[0]

            if status in ["failed", "cancelled", "canceled"]:
                failure = body.get("failure") or body.get("error") or body
                raise RuntimeError(f"Runway task failed: {failure}")

            info(f" => Waiting for Runway task {task_id}: {status or 'unknown'}")
            time.sleep(poll_interval_seconds)

        raise TimeoutError(f"Runway task timed out after {timeout_seconds}s.")

    def download_video(self, video_url: str) -> str:
        output_path = os.path.join(ROOT_DIR, ".mp", f"{uuid4()}-runway-hook.mp4")

        response = requests.get(video_url, timeout=300)
        response.raise_for_status()

        with open(output_path, "wb") as file:
            file.write(response.content)

        info(f' => Downloaded Runway hook video to "{output_path}"')
        return output_path

    def generate_hook_video(
        self,
        prompt: str,
        image_url: str,
        model: str,
        duration: int,
        ratio: str,
        poll_interval_seconds: int,
        timeout_seconds: int,
    ) -> str:
        if not image_url.startswith("http"):
            raise ValueError("Runway image-to-video requires a public image URL.")

        try:
            task_id = self.create_image_to_video_task(
                prompt=prompt,
                image_url=image_url,
                model=model,
                duration=duration,
                ratio=ratio,
            )
            video_url = self.wait_for_task(
                task_id=task_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
            )
            return self.download_video(video_url)
        except HTTPError as exc:
            response = exc.response
            detail = response.text if response is not None else str(exc)
            status_code = response.status_code if response is not None else "unknown"
            warning(f"Runway hook generation failed with HTTP {status_code}: {detail}")
            return None
        except Exception as exc:
            warning(f"Runway hook generation failed: {exc}")
            return None
