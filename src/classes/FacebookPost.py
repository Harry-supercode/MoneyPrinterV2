import os
import platform
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

from config import ROOT_DIR, get_firefox_binary_path
from firefox_profile import apply_firefox_profile
from status import info, success, warning


FACEBOOK_COMPOSER_MARKERS = [
    "what's on your mind",
    "write something",
    "create post",
    "bạn đang nghĩ gì",
    "bạn đang nghĩ gì thế",
    "tạo bài viết",
    "viết gì đó",
]

FACEBOOK_POST_BUTTON_MARKERS = [
    "post",
    "publish",
    "share",
    "đăng",
    "chia sẻ",
]

FACEBOOK_PHOTO_BUTTON_MARKERS = [
    "photo",
    "photo/video",
    "ảnh",
    "ảnh/video",
]


class FacebookPost:
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

    def publish(self, text: str, image_path: str = "") -> dict:
        driver = self.browser
        try:
            info(" => Opening Facebook post composer...")
            driver.get(self.create_url)
            time.sleep(8)

            self._activate_composer(driver)
            editor = self._find_editor(driver)
            self._set_text(driver, editor, text)

            if image_path:
                self._attach_image(driver, image_path)

            self._click_button(driver, FACEBOOK_POST_BUTTON_MARKERS, "Facebook Post", 60)
            time.sleep(self.post_wait_seconds)
            evidence = self._capture_evidence(driver, "facebook-post-after-click")
            verification = self._verify_publish_result(driver)
            if not verification["success"]:
                warning(
                    " => Facebook post click completed but publish could not be verified: "
                    f"{verification['reason']}"
                )
                driver.quit()
                return {
                    "enabled": True,
                    "success": False,
                    "clicked": True,
                    **verification,
                    **evidence,
                }

            success(" => Published Facebook text/image post.")
            driver.quit()
            return {
                "enabled": True,
                "success": True,
                "clicked": True,
                **verification,
                **evidence,
            }
        except Exception:
            traceback.print_exc()
            warning(" => Failed to publish Facebook text/image post.")
            evidence = self._capture_evidence(driver, "facebook-post-error")
            try:
                driver.quit()
            except Exception:
                pass
            return {
                "enabled": True,
                "success": False,
                "clicked": False,
                "reason": "exception",
                **evidence,
            }

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
            f"this profile before publishing Facebook posts: {self.fp_profile_path}."
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
        element = self._find_element_by_markers(
            driver,
            FACEBOOK_COMPOSER_MARKERS,
            "div[role='button'], span, div, textarea, [contenteditable='true']",
            timeout=30,
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", element)
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
                    "div[role='textbox'][contenteditable='true'], [contenteditable='true'], textarea"
                )).filter(isVisible);
                return candidates.length ? candidates[candidates.length - 1] : null;
                """
            )
            return editor or False

        return WebDriverWait(driver, 30).until(find)

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
            if self._try_click_button(driver, FACEBOOK_PHOTO_BUTTON_MARKERS, "Photo/Video", 15):
                time.sleep(2)
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")

        if not file_inputs:
            raise RuntimeError("Could not find Facebook image file input.")

        file_inputs[-1].send_keys(os.path.abspath(image_path))
        time.sleep(8)

    def _find_element_by_markers(
        self,
        driver: webdriver.Firefox,
        markers: list[str],
        selector: str,
        timeout: int,
    ) -> WebElement:
        def find(current_driver: webdriver.Firefox):
            element = current_driver.execute_script(
                """
                const markers = arguments[0].map((value) => String(value).toLowerCase());
                const selector = arguments[1];
                function textFor(el) {
                    return [
                        el.innerText || '',
                        el.textContent || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('placeholder') || '',
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
                const candidates = Array.from(document.querySelectorAll(selector))
                    .filter(isVisible)
                    .filter((el) => markers.some((marker) => textFor(el).includes(marker)));
                return candidates.length ? candidates[candidates.length - 1] : null;
                """,
                markers,
                selector,
            )
            return element or False

        return WebDriverWait(driver, timeout).until(find)

    def _click_button(
        self,
        driver: webdriver.Firefox,
        markers: list[str],
        label: str,
        timeout: int,
    ) -> None:
        button = self._find_element_by_markers(
            driver,
            markers,
            "div[role='button'], button, a[role='button']",
            timeout,
        )
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
            warning(f"Could not click optional Facebook {label} button: {exc}")
            return False

    def _verify_publish_result(self, driver: webdriver.Firefox) -> dict:
        page_text = ""
        try:
            page_text = driver.execute_script("return document.body.innerText || '';") or ""
        except Exception:
            page_text = ""

        normalized = page_text.lower()
        error_markers = [
            "something went wrong",
            "try again",
            "couldn't post",
            "could not post",
            "we restrict certain activity",
            "đã xảy ra lỗi",
            "thử lại",
            "không thể đăng",
            "bị hạn chế",
        ]
        if any(marker in normalized for marker in error_markers):
            return {"success": False, "reason": "facebook_error_visible"}

        composer_open = self._composer_is_open(driver)
        if composer_open:
            return {"success": False, "reason": "composer_still_open_after_click"}

        return {"success": True, "reason": "composer_closed_no_visible_error"}

    def _composer_is_open(self, driver: webdriver.Firefox) -> bool:
        try:
            return bool(
                driver.execute_script(
                    """
                    function isVisible(el) {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 40 && rect.height > 20 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden' &&
                            Number(style.opacity || 1) > 0;
                    }
                    const dialogs = Array.from(document.querySelectorAll("[role='dialog'], [aria-modal='true']"))
                        .filter(isVisible);
                    const textboxes = Array.from(document.querySelectorAll(
                        "div[role='textbox'][contenteditable='true'], [contenteditable='true'], textarea"
                    )).filter(isVisible);
                    return dialogs.length > 0 && textboxes.length > 0;
                    """
                )
            )
        except Exception:
            return False

    def _capture_evidence(self, driver: webdriver.Firefox, label: str) -> dict:
        evidence_dir = Path(ROOT_DIR) / "output" / "social_posts" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = evidence_dir / f"{timestamp}-{label}.png"
        html_path = evidence_dir / f"{timestamp}-{label}.html"
        evidence = {
            "current_url": "",
            "screenshot_path": str(screenshot_path),
            "html_path": str(html_path),
        }

        try:
            evidence["current_url"] = driver.current_url
        except Exception:
            pass

        try:
            driver.save_screenshot(str(screenshot_path))
        except Exception as exc:
            evidence["screenshot_error"] = str(exc)

        try:
            html_path.write_text(driver.page_source, encoding="utf-8", errors="replace")
        except Exception as exc:
            evidence["html_error"] = str(exc)

        return evidence
