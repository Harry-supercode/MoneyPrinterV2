import os
import platform
import subprocess
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

from config import get_firefox_binary_path
from firefox_profile import apply_firefox_profile
from status import info, success, warning


YOUTUBE_COMPOSER_MARKERS = [
    "create post",
    "post",
    "community",
    "tạo bài đăng",
    "bài đăng",
    "cộng đồng",
]

YOUTUBE_PUBLISH_MARKERS = [
    "post",
    "publish",
    "schedule",
    "đăng",
    "xuất bản",
    "lên lịch",
]

YOUTUBE_IMAGE_MARKERS = [
    "image",
    "photo",
    "add image",
    "ảnh",
    "thêm ảnh",
]


class YouTubeCommunityPost:
    def __init__(self, fp_profile_path: str, create_url: str, post_wait_seconds: int = 12):
        self.fp_profile_path = fp_profile_path
        self.create_url = create_url
        self.post_wait_seconds = post_wait_seconds

        if not os.path.isdir(self.fp_profile_path):
            raise ValueError(f"Firefox profile path does not exist: {self.fp_profile_path}")

        self._assert_firefox_profile_available()

        self.options = Options()
        firefox_binary_path = get_firefox_binary_path()
        if firefox_binary_path:
            self.options.binary_location = firefox_binary_path
        apply_firefox_profile(self.options, self.fp_profile_path)

        self.service = Service(GeckoDriverManager().install())
        self.browser = webdriver.Firefox(service=self.service, options=self.options)

    def publish(self, text: str, image_path: str = "") -> bool:
        driver = self.browser
        try:
            info(" => Opening YouTube Community post composer...")
            driver.get(self.create_url)
            time.sleep(8)

            self._activate_composer(driver)
            editor = self._find_editor(driver)
            self._set_text(driver, editor, text)

            if image_path:
                self._attach_image(driver, image_path)

            self._click_button(driver, YOUTUBE_PUBLISH_MARKERS, "YouTube Community Post", 60)
            time.sleep(self.post_wait_seconds)
            success(" => Published YouTube Community post.")
            driver.quit()
            return True
        except Exception:
            traceback.print_exc()
            warning(" => Failed to publish YouTube Community post.")
            try:
                driver.quit()
            except Exception:
                pass
            return False

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
            f"this profile before publishing YouTube Community posts: {self.fp_profile_path}."
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
            return "\n".join(
                line
                for line in output.splitlines()
                if any(name in line.lower() for name in ["firefox", "plugin-container", "geckodriver"])
            )
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

    def _activate_composer(self, driver: webdriver.Firefox) -> None:
        if self._try_click_button(driver, YOUTUBE_COMPOSER_MARKERS, "Create Post", 20):
            time.sleep(3)

    def _find_editor(self, driver: webdriver.Firefox) -> WebElement:
        def find(current_driver: webdriver.Firefox):
            editor = current_driver.execute_script(
                """
                function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 40 && rect.height > 20 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        Number(style.opacity || 1) > 0;
                }
                const candidates = Array.from(document.querySelectorAll(
                    "textarea, ytcp-social-suggestions-textbox, [contenteditable='true'], div[role='textbox']"
                )).filter(isVisible);
                return candidates.length ? candidates[candidates.length - 1] : null;
                """
            )
            return editor or False

        return WebDriverWait(driver, 45).until(find)

    def _set_text(self, driver: webdriver.Firefox, editor: WebElement, text: str) -> None:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
        editor.click()
        time.sleep(0.5)
        modifier_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        ActionChains(driver).key_down(modifier_key).send_keys("a").key_up(modifier_key).perform()
        editor.send_keys(Keys.BACKSPACE)
        time.sleep(0.3)
        editor.send_keys(text)
        time.sleep(1)

    def _attach_image(self, driver: webdriver.Firefox, image_path: str) -> None:
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")

        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        if not file_inputs:
            if self._try_click_button(driver, YOUTUBE_IMAGE_MARKERS, "Image", 15):
                time.sleep(2)
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")

        if not file_inputs:
            raise RuntimeError("Could not find YouTube Community image file input.")

        file_inputs[-1].send_keys(os.path.abspath(image_path))
        time.sleep(8)

    def _click_button(
        self,
        driver: webdriver.Firefox,
        markers: list[str],
        label: str,
        timeout: int,
    ) -> None:
        button = self._find_button(driver, markers, timeout)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", button)

    def _try_click_button(
        self,
        driver: webdriver.Firefox,
        markers: list[str],
        label: str,
        timeout: int,
    ) -> bool:
        try:
            self._click_button(driver, markers, label, timeout)
            return True
        except Exception as exc:
            warning(f"Could not click optional YouTube {label} button: {exc}")
            return False

    def _find_button(
        self,
        driver: webdriver.Firefox,
        markers: list[str],
        timeout: int,
    ) -> WebElement:
        def find(current_driver: webdriver.Firefox):
            button = current_driver.execute_script(
                """
                const markers = arguments[0].map((value) => String(value).toLowerCase());
                function textFor(el) {
                    return [
                        el.innerText || '',
                        el.textContent || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || ''
                    ].join(' ').toLowerCase();
                }
                function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 20 && rect.height > 12 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        Number(style.opacity || 1) > 0;
                }
                const candidates = Array.from(document.querySelectorAll(
                    "button, tp-yt-paper-button, ytcp-button, div[role='button'], a[role='button']"
                ))
                    .filter(isVisible)
                    .filter((el) => markers.some((marker) => textFor(el).includes(marker)));
                return candidates.length ? candidates[candidates.length - 1] : null;
                """,
                markers,
            )
            return button or False

        return WebDriverWait(driver, timeout).until(find)
