import json
import os

import requests

from llm_provider import generate_text, get_active_model
from status import info, warning


class DubTranslator:
    def __init__(self, config: dict) -> None:
        self.config = config

    def translate(self, segments: list[dict], run_dir: str) -> list[dict]:
        target_language = self._target_language_name()
        translated_by_provider = self._translate_with_configured_provider(segments)
        translated = []
        for segment in segments:
            text = segment.get("text", "")
            text_vi = segment.get("text_vi", "") or translated_by_provider.get(segment["index"], "")
            if not text_vi and get_active_model():
                text_vi = generate_text(
                    f"Translate this video transcript segment to natural {target_language}. "
                    f"Return only the translation:\n{text}"
                )
            if not text_vi:
                text_vi = text

            translated.append({**segment, "text_vi": text_vi.strip()})

        transcript_path = os.path.join(run_dir, f"transcript_{self._target_language_code()}.json")
        with open(transcript_path, "w", encoding="utf-8") as file:
            json.dump(translated, file, ensure_ascii=False, indent=2)

        return translated

    def _translate_with_configured_provider(self, segments: list[dict]) -> dict[int, str]:
        translation_config = self.config.get("translation", {})
        providers = []

        for provider in [
            translation_config.get("primary", ""),
            translation_config.get("fallback", ""),
        ]:
            if provider and provider not in providers:
                providers.append(provider)

        for provider in providers:
            try:
                if provider == "gemini":
                    return self._translate_with_gemini(segments, translation_config)
                if provider == "groq":
                    return self._translate_with_groq(segments, translation_config)
            except Exception as exc:
                warning(f"Dub translation provider '{provider}' failed: {exc}")

        return {}

    def _translate_with_gemini(
        self,
        segments: list[dict],
        translation_config: dict,
    ) -> dict[int, str]:
        api_key = translation_config.get("gemini_api_key", "")
        if not api_key:
            raise RuntimeError("Gemini API key is empty")

        model = translation_config.get("gemini_model", "gemini-2.0-flash")
        info(f" => Translating transcript with Gemini model={model}")
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": self._translation_prompt(segments),
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse_translation_response(text)

    def _translate_with_groq(
        self,
        segments: list[dict],
        translation_config: dict,
    ) -> dict[int, str]:
        api_key = translation_config.get("groq_api_key", "")
        if not api_key:
            raise RuntimeError("Groq API key is empty")

        model = translation_config.get("groq_model", "llama-3.3-70b-versatile")
        info(f" => Translating transcript with Groq model={model}")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You translate video transcript segments to natural "
                            f"{self._target_language_name()}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._translation_prompt(segments),
                    },
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return self._parse_translation_response(text)

    def _translation_prompt(self, segments: list[dict]) -> str:
        return self._translation_prompt_for_language(
            segments,
            self._target_language_name(),
        )

    def _translation_prompt_for_language(self, segments: list[dict], language_name: str) -> str:
        payload = [
            {
                "index": int(segment["index"]),
                "text": str(segment.get("text", "")).strip(),
            }
            for segment in segments
        ]
        return (
            f"Translate each transcript segment to natural spoken {language_name} for dubbing. "
            "Preserve meaning, keep each segment concise enough for the original timing, "
            "and return only JSON in this shape: "
            '{"segments":[{"index":1,"text_vi":"..."}]}.\n'
            f"Segments:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _target_language_code(self) -> str:
        return str(self.config.get("language", "vi")).strip().lower() or "vi"

    def _target_language_name(self) -> str:
        language = self._target_language_code()
        if language.startswith("en"):
            return "English"
        if language.startswith("vi"):
            return "Vietnamese"
        return language

    @staticmethod
    def _parse_translation_response(text: str) -> dict[int, str]:
        cleaned = str(text).replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        items = parsed.get("segments", parsed if isinstance(parsed, list) else [])
        return {
            int(item["index"]): str(item.get("text_vi", "")).strip()
            for item in items
            if str(item.get("text_vi", "")).strip()
        }
