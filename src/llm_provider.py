import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import ollama

from config import get_ollama_base_url
from status import info

_selected_model: str | None = None


def _client() -> ollama.Client:
    return ollama.Client(host=get_ollama_base_url())


def _ollama_is_reachable(base_url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout):
            return True
    except (OSError, URLError):
        return False


def _ensure_ollama_available(wait_seconds: float = 15.0) -> None:
    base_url = get_ollama_base_url()
    if _ollama_is_reachable(base_url):
        return

    hostname = (urlparse(base_url).hostname or "").lower()
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ConnectionError(f"Ollama is not reachable at {base_url}")

    executable = shutil.which("ollama")
    if not executable:
        raise ConnectionError(
            "Ollama is not running and the 'ollama' executable was not found in PATH"
        )

    info(f" => Ollama is offline; starting {executable} serve...")
    subprocess.Popen(
        [executable, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if _ollama_is_reachable(base_url):
            return
        time.sleep(0.25)

    raise ConnectionError(f"Ollama did not become ready at {base_url} within {wait_seconds:g}s")


def list_models() -> list[str]:
    """
    Lists all models available on the local Ollama server.

    Returns:
        models (list[str]): Sorted list of model names.
    """
    _ensure_ollama_available()
    response = _client().list()
    return sorted(m.model for m in response.models)


def select_model(model: str) -> None:
    """
    Sets the model to use for all subsequent generate_text calls.

    Args:
        model (str): An Ollama model name (must be already pulled).
    """
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    """
    Returns the currently selected model, or None if none has been selected.
    """
    return _selected_model


def generate_text(prompt: str, model_name: str = None) -> str:
    """
    Generates text using the local Ollama server.

    Args:
        prompt (str): User prompt
        model_name (str): Optional model name override

    Returns:
        response (str): Generated text
    """
    model = model_name or _selected_model
    if not model:
        raise RuntimeError(
            "No Ollama model selected. Call select_model() first or pass model_name."
        )

    _ensure_ollama_available()
    response = _client().chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"].strip()
