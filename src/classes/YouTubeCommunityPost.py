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


YOUTUBE_COMPOSER_MARKERS = [
    "create post",
    "post",
    "community",
    "tạo bài đăng",
    "bài đăng",
    "cộng đồng",
    "bạn đang nghĩ gì",
    "what are you thinking",
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

    def publish(self, text: str, image_path: str = "") -> dict:
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

            self._capture_evidence(driver, "youtube-community-before-click")
            self._click_publish_button(driver, timeout=60)
            wait_seconds = self._post_publish_wait_seconds(image_path)
            info(f" => Waiting {wait_seconds}s for YouTube Community post to settle...")
            time.sleep(wait_seconds)
            evidence = self._capture_evidence(driver, "youtube-community-after-click")
            verification = self._verify_publish_result(driver)
            if not verification["success"]:
                warning(
                    " => YouTube Community post click completed but publish could not be verified: "
                    f"{verification['reason']}"
                )
                if self._hold_browser_open_if_requested(
                    driver,
                    f"YouTube Community publish verification failed: {verification['reason']}",
                ):
                    return {
                        "enabled": True,
                        "success": False,
                        "clicked": True,
                        "browser_left_open": True,
                        **verification,
                        **evidence,
                    }
                driver.quit()
                return {
                    "enabled": True,
                    "success": False,
                    "clicked": True,
                    **verification,
                    **evidence,
                }

            success(" => Published YouTube Community post.")
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
            warning(" => Failed to publish YouTube Community post.")
            evidence = self._capture_evidence(driver, "youtube-community-error")
            if self._hold_browser_open_if_requested(driver, "YouTube Community publish exception"):
                return {
                    "enabled": True,
                    "success": False,
                    "clicked": False,
                    "reason": "exception",
                    "browser_left_open": True,
                    **evidence,
                }
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

    def _post_publish_wait_seconds(self, image_path: str = "") -> int:
        configured_hold = self._env_int("MPV2_YOUTUBE_COMMUNITY_POST_HOLD_SECONDS", 0)
        if image_path:
            return max(self.post_wait_seconds, 60, configured_hold)
        return max(self.post_wait_seconds, 30, configured_hold)

    def _hold_browser_open_if_requested(
        self,
        driver: webdriver.Firefox,
        reason: str,
    ) -> bool:
        hold_seconds = self._env_int("MPV2_YOUTUBE_COMMUNITY_KEEP_BROWSER_OPEN_SECONDS", 0)
        if hold_seconds <= 0:
            return False

        hold_seconds = min(hold_seconds, 3600)
        warning(
            f" => Keeping Firefox open for {hold_seconds}s after {reason}. "
            "Do not close the VNC/browser while YouTube finishes the post."
        )
        try:
            self._capture_evidence(driver, "youtube-community-browser-left-open")
        except Exception:
            pass
        time.sleep(hold_seconds)
        return True

    def _env_int(self, name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

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
        if self._click_community_prompt(driver):
            time.sleep(2)
            return
        if self._try_click_button(driver, YOUTUBE_COMPOSER_MARKERS, "Create Post", 20):
            time.sleep(3)

    def _click_community_prompt(self, driver: webdriver.Firefox) -> bool:
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

                    function textFor(el) {
                        return [
                            el.innerText || '',
                            el.textContent || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('placeholder') || ''
                        ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
                    }

                    function clickElement(el) {
                        const rect = el.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        el.scrollIntoView({block: 'center'});
                        for (const eventName of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                            el.dispatchEvent(new MouseEvent(eventName, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: x,
                                clientY: y
                            }));
                        }
                        return true;
                    }

                    const promptMarkers = [
                        'bạn đang nghĩ gì',
                        'ban dang nghi gi',
                        'what are you thinking',
                        'share something'
                    ];
                    const candidates = Array.from(document.querySelectorAll(
                        "textarea, [contenteditable='true'], div[role='textbox'], ytcp-social-suggestions-textbox, yt-formatted-string, span, div"
                    ))
                        .filter(isVisible)
                        .map((el) => ({el, text: textFor(el), rect: el.getBoundingClientRect()}))
                        .filter((item) => promptMarkers.some((marker) => item.text.includes(marker)))
                        .filter((item) => !item.text.includes('tìm kiếm') && !item.text.includes('search'))
                        .sort((a, b) => {
                            const areaA = a.rect.width * a.rect.height;
                            const areaB = b.rect.width * b.rect.height;
                            return areaB - areaA;
                        });

                    if (!candidates.length) return false;
                    let target = candidates[0].el.closest("div[role='button'], ytd-backstage-post-thread-renderer, ytd-backstage-post-dialog-renderer") || candidates[0].el;
                    return clickElement(target);
                    """
                )
            )
        except Exception:
            return False

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
                function textFor(el) {
                    return [
                        el.innerText || '',
                        el.textContent || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('placeholder') || ''
                    ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
                }
                function isEditor(el) {
                    if (!el || !isVisible(el)) return false;
                    const tag = String(el.tagName || '').toLowerCase();
                    const role = String(el.getAttribute('role') || '').toLowerCase();
                    const text = textFor(el);
                    if (text.includes('tìm kiếm') || text.includes('search')) return false;
                    return tag === 'textarea' ||
                        el.isContentEditable ||
                        role === 'textbox' ||
                        tag === 'ytcp-social-suggestions-textbox' ||
                        tag === 'yt-emoji-input';
                }
                if (isEditor(document.activeElement)) return document.activeElement;
                const candidates = Array.from(document.querySelectorAll(
                    "textarea, ytcp-social-suggestions-textbox, yt-emoji-input, [contenteditable='true'], div[role='textbox'], [aria-label*='Bạn đang nghĩ'], [aria-label*='What are you thinking']"
                )).filter(isEditor);
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
        if not self._editor_has_text(driver, text):
            self._set_text_by_dom(driver, editor, text)
            time.sleep(1)
        if not self._editor_has_text(driver, text):
            raise RuntimeError("YouTube Community editor did not accept the post text.")

    def _editor_has_text(self, driver: webdriver.Firefox, expected_text: str) -> bool:
        try:
            sample = expected_text.strip()[:80]
            if not sample:
                return True
            return bool(
                driver.execute_script(
                    """
                    const sample = arguments[0];
                    const text = (document.body.innerText || document.body.textContent || '');
                    return text.includes(sample);
                    """,
                    sample,
                )
            )
        except Exception:
            return False

    def _set_text_by_dom(
        self,
        driver: webdriver.Firefox,
        editor: WebElement,
        text: str,
    ) -> None:
        driver.execute_script(
            """
            const el = arguments[0];
            const value = arguments[1];
            el.focus();
            if ('value' in el) {
                el.value = value;
            } else if (el.isContentEditable) {
                el.innerText = value;
            } else {
                const editable = el.querySelector("[contenteditable='true'], textarea, div[role='textbox']") || el;
                if ('value' in editable) {
                    editable.value = value;
                } else {
                    editable.innerText = value;
                }
            }
            for (const eventName of ['beforeinput', 'input', 'change', 'keyup']) {
                el.dispatchEvent(new Event(eventName, {bubbles: true}));
            }
            """,
            editor,
            text,
        )

    def _attach_image(self, driver: webdriver.Firefox, image_path: str) -> None:
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")

        self._try_click_button(driver, YOUTUBE_IMAGE_MARKERS, "Image", 15)
        time.sleep(2)
        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")

        if not file_inputs:
            raise RuntimeError("Could not find YouTube Community image file input.")

        image_inputs = [
            file_input
            for file_input in file_inputs
            if "image" in (file_input.get_attribute("accept") or "").lower()
        ]
        target_input = image_inputs[-1] if image_inputs else file_inputs[-1]
        target_input.send_keys(os.path.abspath(image_path))
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

    def _click_publish_button(self, driver: webdriver.Firefox, timeout: int = 60) -> None:
        button = self._find_button(driver, YOUTUBE_PUBLISH_MARKERS, timeout, prefer_bottom=True)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(1)
        for attempt in range(3):
            driver.execute_script("arguments[0].click();", button)
            time.sleep(3)
            if not self._composer_is_open(driver):
                return
            if attempt < 2:
                button = self._find_button(driver, YOUTUBE_PUBLISH_MARKERS, 15, prefer_bottom=True)

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
        prefer_bottom: bool = False,
    ) -> WebElement:
        def find(current_driver: webdriver.Firefox):
            button = current_driver.execute_script(
                """
                const markers = arguments[0].map((value) => String(value).toLowerCase());
                const preferBottom = Boolean(arguments[1]);
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
                function isEnabled(el) {
                    const style = window.getComputedStyle(el);
                    return !el.disabled &&
                        el.getAttribute('disabled') === null &&
                        el.getAttribute('aria-disabled') !== 'true' &&
                        !String(el.getAttribute('class') || '').toLowerCase().includes('disabled') &&
                        style.pointerEvents !== 'none';
                }
                const candidates = Array.from(document.querySelectorAll(
                    "button, tp-yt-paper-button, ytcp-button, div[role='button'], a[role='button']"
                ))
                    .filter(isVisible)
                    .filter(isEnabled)
                    .map((el) => {
                        const text = textFor(el);
                        const rect = el.getBoundingClientRect();
                        let score = 0;
                        if (markers.some((marker) => text.includes(marker))) score += 300;
                        if (text === 'post' || text === 'đăng') score += 600;
                        if (text === 'publish' || text === 'xuất bản') score += 500;
                        if (text.includes('schedule') || text.includes('lên lịch')) score -= 250;
                        if (preferBottom) score += Math.round(rect.top / 6);
                        return {el, text, score};
                    })
                    .filter((item) => item.score >= 300)
                    .sort((a, b) => b.score - a.score);
                return candidates.length ? candidates[0].el : null;
                """,
                markers,
                prefer_bottom,
            )
            return button or False

        return WebDriverWait(driver, timeout).until(find)

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
            "couldn't create post",
            "could not create post",
            "couldn't post",
            "could not post",
            "đã xảy ra lỗi",
            "thử lại",
            "không thể đăng",
        ]
        if any(marker in normalized for marker in error_markers):
            return {"success": False, "reason": "youtube_error_visible"}

        if self._composer_is_open(driver):
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
                    const editors = Array.from(document.querySelectorAll(
                        "textarea, ytcp-social-suggestions-textbox, [contenteditable='true'], div[role='textbox']"
                    )).filter(isVisible);
                    return editors.length > 0;
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
        except Exception:
            pass

        try:
            html_path.write_text(driver.page_source, encoding="utf-8")
        except Exception:
            pass

        return evidence
