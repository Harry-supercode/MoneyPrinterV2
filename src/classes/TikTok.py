import os
import subprocess
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException

from config import get_firefox_binary_path
from firefox_profile import apply_firefox_profile
from status import info, success, warning


class TikTok:
    def __init__(self, fp_profile_path: str):
        self.fp_profile_path = fp_profile_path

        if not os.path.isdir(self.fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist: {self.fp_profile_path}"
            )

        self._assert_firefox_profile_available()

        self.options = Options()
        firefox_binary_path = get_firefox_binary_path()
        if firefox_binary_path:
            self.options.binary_location = firefox_binary_path

        # TikTok upload needs visible browser for now
        # self.options.add_argument("--headless")

        apply_firefox_profile(self.options, self.fp_profile_path)

        self.service = Service(GeckoDriverManager().install())

        self.browser = webdriver.Firefox(
            service=self.service,
            options=self.options,
        )

    def _assert_firefox_profile_available(self) -> None:
        lock_path = os.path.join(self.fp_profile_path, ".parentlock")
        if not os.path.exists(lock_path):
            return

        active_process = self._find_firefox_process_using_profile()
        if not active_process:
            warning(
                f"Found stale Firefox profile lock, but no active Firefox process: {lock_path}"
            )
            self._clear_stale_firefox_locks()
            return

        raise RuntimeError(
            "Firefox profile is currently in use. Close all Firefox windows that use "
            f"this profile before uploading to TikTok: {self.fp_profile_path}. "
            "You can run `pkill -f Firefox` if no upload session is active."
        )

    def _find_firefox_process_using_profile(self) -> str:
        try:
            result = subprocess.run(
                ["pgrep", "-fl", self.fp_profile_path],
                check=False,
                capture_output=True,
                text=True,
            )
            output = result.stdout.strip()
            if not output:
                return ""

            process_lines = [
                line
                for line in output.splitlines()
                if any(name in line.lower() for name in ["firefox", "plugin-container", "geckodriver"])
            ]
            return "\n".join(process_lines)
        except Exception:
            return ""

    def _clear_stale_firefox_locks(self) -> None:
        for lock_name in (".parentlock", "lock"):
            lock_path = os.path.join(self.fp_profile_path, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except OSError as exc:
                    warning(f"Could not remove stale Firefox lock {lock_path}: {exc}")

    def upload_video(self, video_path: str, caption: str = "") -> bool:
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        driver = self.browser

        try:
            info(" => Opening TikTok upload page...")
            driver.get("https://www.tiktok.com/upload")
            time.sleep(15)

            info(" => Uploading TikTok video file...")

            file_input = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
            )

            file_input.send_keys(os.path.abspath(video_path))

            info(" => Waiting for TikTok video upload processing...")
            time.sleep(45)

            if caption:
                info(" => Setting TikTok caption...")

                caption_boxes = driver.find_elements(
                    By.XPATH,
                    "//div[@contenteditable='true']"
                )

                if caption_boxes:
                    caption_boxes[0].click()
                    time.sleep(1)

                    caption_boxes[0].send_keys(Keys.COMMAND, "a")
                    time.sleep(0.5)

                    caption_boxes[0].send_keys(Keys.BACKSPACE)
                    time.sleep(0.5)

                    caption_boxes[0].send_keys(caption[:2200])
                else:
                    warning("Could not find TikTok caption box. Skipping caption.")

            info(" => Looking for TikTok Post button...")

            post_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(., 'Post') or contains(., 'Publish')]"
            )

            if not post_buttons:
                raise Exception("Could not find TikTok Post/Publish button")

            time.sleep(5)
            self._click_post_button(driver, post_buttons[-1])

            info(" => Waiting for TikTok publish...")
            time.sleep(20)

            success(" => Uploaded TikTok video.")

            driver.quit()
            return True

        except Exception:
            traceback.print_exc()
            warning(" => Failed to upload TikTok video.")

            try:
                driver.quit()
            except Exception:
                pass

            return False

    def _click_post_button(self, driver: webdriver.Firefox, post_button) -> None:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post_button)
        time.sleep(1)
        try:
            post_button.click()
            return
        except ElementClickInterceptedException:
            warning("TikTok Post button was covered by a suggestion popup. Closing overlay and retrying.")

        try:
            driver.switch_to.active_element.send_keys(Keys.ESCAPE)
            time.sleep(1)
        except Exception:
            pass

        try:
            driver.execute_script(
                """
                for (const selector of [
                    '[id^="mention-option"]',
                    '[class*="suggestion"]',
                    '[class*="Suggestion"]'
                ]) {
                    document.querySelectorAll(selector).forEach((el) => {
                        el.style.display = 'none';
                        el.style.pointerEvents = 'none';
                    });
                }
                """
            )
        except Exception:
            pass

        driver.execute_script("arguments[0].click();", post_button)
