import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT_DIR / "scripts" / "random_scheduler.py"

spec = importlib.util.spec_from_file_location("random_scheduler", SCHEDULER_PATH)
random_scheduler = importlib.util.module_from_spec(spec)
sys.modules["random_scheduler"] = random_scheduler
assert spec.loader is not None
spec.loader.exec_module(random_scheduler)


class RandomSchedulerLaunchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mp_dir = self.root / ".mp"
        self.mp_dir.mkdir()
        self.log_path = self.root / "dub_cron.log"
        self.lock_path = self.root / "dub.lock"

        self.original_root = random_scheduler.ROOT
        self.original_mp_dir = random_scheduler.MP_DIR
        self.original_log_path = random_scheduler.LOG_PATH
        self.original_job_health = random_scheduler.JOB_HEALTH

        random_scheduler.ROOT = self.root
        random_scheduler.MP_DIR = self.mp_dir
        random_scheduler.LOG_PATH = self.root / "random_scheduler.log"
        random_scheduler.JOB_HEALTH = {
            "dub_pipeline": {
                "lock": self.lock_path,
                "log": self.log_path,
                "start_text": "START dub_pipeline",
                "process_pattern": "this-process-should-not-exist",
            }
        }

    def tearDown(self) -> None:
        random_scheduler.ROOT = self.original_root
        random_scheduler.MP_DIR = self.original_mp_dir
        random_scheduler.LOG_PATH = self.original_log_path
        random_scheduler.JOB_HEALTH = self.original_job_health
        self.tmp.cleanup()

    def write_launcher(self, body: str) -> str:
        launcher = self.root / "launcher.sh"
        launcher.write_text("#!/bin/zsh\n" + body, encoding="utf-8")
        launcher.chmod(0o755)
        return str(launcher)

    def base_slot(self) -> dict:
        return {
            "id": "20260721-01",
            "job": "dub_pipeline",
            "platforms": {"facebook_reels": False, "tiktok": False},
            "override_platform_uploads": False,
        }

    def test_marks_launched_when_runner_starts_real_job(self) -> None:
        launcher = self.write_launcher(
            f"mkdir '{self.lock_path}'\n"
            f"echo '[test] START dub_pipeline pid=$$' >> '{self.log_path}'\n"
        )
        slot = self.base_slot()

        result = random_scheduler.launch_slot(
            slot,
            {"launchers": {"dub_pipeline": launcher}, "launch_probe_seconds": 1},
        )

        self.assertTrue(result)
        self.assertEqual(slot["status"], "launched")
        self.assertIn("launcher_pid", slot)

    def test_marks_failed_when_runner_exits_before_job_starts(self) -> None:
        launcher = self.write_launcher("exit 7\n")
        slot = self.base_slot()

        result = random_scheduler.launch_slot(
            slot,
            {"launchers": {"dub_pipeline": launcher}, "launch_probe_seconds": 1},
        )

        self.assertFalse(result)
        self.assertEqual(slot["status"], "failed")
        self.assertEqual(slot["launcher_exit"], 7)

    def test_defers_when_runner_reports_active_job(self) -> None:
        launcher = self.write_launcher("exit 75\n")
        slot = self.base_slot()

        result = random_scheduler.launch_slot(
            slot,
            {"launchers": {"dub_pipeline": launcher}, "launch_probe_seconds": 1},
        )

        self.assertFalse(result)
        self.assertEqual(slot["status"], "pending")
        self.assertEqual(slot["launcher_exit"], 75)
        self.assertIn("defer_reason", slot)


if __name__ == "__main__":
    unittest.main()
