import os
import sys
import unittest
from unittest.mock import Mock, patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

sys.modules.pop("llm_provider", None)
sys.modules.pop("classes.DubTopicPlanner", None)
sys.modules.pop("classes.DubMetadata", None)
sys.modules.pop("classes.DubPipeline", None)
import dub_cron


class DubCronTests(unittest.TestCase):
    def test_keyboard_interrupt_exits_without_traceback(self) -> None:
        pipeline = Mock()
        pipeline.run.side_effect = KeyboardInterrupt

        with (
            patch.object(dub_cron, "DubPipeline", return_value=pipeline),
            patch.object(dub_cron, "warning") as warning_mock,
            patch.object(sys, "argv", ["dub_cron.py"]),
        ):
            dub_cron.main()

        warning_mock.assert_called_once_with("Dub pipeline cancelled by user.")


if __name__ == "__main__":
    unittest.main()
