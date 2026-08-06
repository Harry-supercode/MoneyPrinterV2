import os
import sys
import unittest
from unittest.mock import Mock, patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

sys.modules.pop("llm_provider", None)
import llm_provider


class OllamaAvailabilityTests(unittest.TestCase):
    def test_reachable_server_does_not_start_process(self) -> None:
        with (
            patch.object(llm_provider, "_ollama_is_reachable", return_value=True),
            patch.object(llm_provider.subprocess, "Popen") as popen_mock,
        ):
            llm_provider._ensure_ollama_available()

        popen_mock.assert_not_called()

    def test_local_server_is_started_and_waited_for(self) -> None:
        with (
            patch.object(llm_provider, "get_ollama_base_url", return_value="http://127.0.0.1:11434"),
            patch.object(llm_provider, "_ollama_is_reachable", side_effect=[False, False, True]),
            patch.object(llm_provider.shutil, "which", return_value="/opt/homebrew/bin/ollama"),
            patch.object(llm_provider.subprocess, "Popen") as popen_mock,
            patch.object(llm_provider.time, "sleep"),
        ):
            llm_provider._ensure_ollama_available(wait_seconds=1)

        popen_mock.assert_called_once_with(
            ["/opt/homebrew/bin/ollama", "serve"],
            stdout=llm_provider.subprocess.DEVNULL,
            stderr=llm_provider.subprocess.DEVNULL,
            start_new_session=True,
        )

    def test_remote_server_failure_does_not_start_local_process(self) -> None:
        with (
            patch.object(llm_provider, "get_ollama_base_url", return_value="https://ollama.example.com"),
            patch.object(llm_provider, "_ollama_is_reachable", return_value=False),
            patch.object(llm_provider.subprocess, "Popen") as popen_mock,
        ):
            with self.assertRaisesRegex(ConnectionError, "not reachable"):
                llm_provider._ensure_ollama_available()

        popen_mock.assert_not_called()

    def test_generate_text_checks_server_before_chat(self) -> None:
        response = {"message": {"content": "OLLAMA_OK"}}
        client = Mock()
        client.chat.return_value = response

        with (
            patch.object(llm_provider, "_ensure_ollama_available") as ensure_mock,
            patch.object(llm_provider, "_client", return_value=client),
        ):
            result = llm_provider.generate_text("test", model_name="llama3.2:latest")

        self.assertEqual(result, "OLLAMA_OK")
        ensure_mock.assert_called_once_with()

    def test_list_models_checks_server_before_request(self) -> None:
        model = Mock()
        model.model = "llama3.2:latest"
        response = Mock()
        response.models = [model]
        client = Mock()
        client.list.return_value = response

        with (
            patch.object(llm_provider, "_ensure_ollama_available") as ensure_mock,
            patch.object(llm_provider, "_client", return_value=client),
        ):
            result = llm_provider.list_models()

        self.assertEqual(result, ["llama3.2:latest"])
        ensure_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
