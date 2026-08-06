import os
import shutil

from config import ROOT_DIR
from status import info, success, warning


class DubRunCleanup:
    def __init__(self, config: dict) -> None:
        self.config = config

    def cleanup_after_successful_upload(self, run_dir: str, upload_result: dict) -> bool:
        if not self.config.get("cleanup_after_successful_upload"):
            info(" => Dub cleanup disabled; keeping run artifacts.")
            return False

        enabled_results = [
            result
            for result in upload_result.values()
            if isinstance(result, dict) and result.get("enabled")
        ]
        if not enabled_results:
            info(" => No dub upload target enabled; keeping run artifacts for review.")
            return False

        failed_results = [result for result in enabled_results if not result.get("success")]
        if failed_results:
            warning(" => Dub upload did not fully succeed; keeping run artifacts for debug.")
            return False

        if not self._is_safe_run_dir(run_dir):
            warning(f" => Refusing to cleanup unsafe dub run dir: {run_dir}")
            return False

        shutil.rmtree(run_dir)
        success(f" => Cleaned up dub run artifacts after successful upload: {run_dir}")
        return True

    def _is_safe_run_dir(self, run_dir: str) -> bool:
        resolved_run_dir = os.path.realpath(run_dir)
        output_root = self.config.get("output_root", "output/dub_pipeline")
        if not os.path.isabs(output_root):
            output_root = os.path.join(ROOT_DIR, output_root)

        resolved_output_root = os.path.realpath(output_root)
        country = self.config.get("country", "VN")
        resolved_country_root = os.path.realpath(os.path.join(resolved_output_root, country))

        if resolved_run_dir in {resolved_output_root, resolved_country_root, ROOT_DIR, "/"}:
            return False

        return resolved_run_dir.startswith(resolved_country_root + os.sep)
