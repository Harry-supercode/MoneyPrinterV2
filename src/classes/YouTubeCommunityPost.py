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
            self._set_text_in_active_composer(driver, text)
            self._install_youtube_dom_helpers(driver)

            if image_path:
                self._attach_image(driver, image_path, text)

            self._capture_evidence(driver, "youtube-community-before-click")
            self._click_publish_button(driver, text, timeout=60)
            wait_seconds = self._post_publish_wait_seconds(image_path)
            info(f" => Waiting {wait_seconds}s for YouTube Community post to settle...")
            time.sleep(wait_seconds)
            evidence = self._capture_evidence(driver, "youtube-community-after-click")
            verification = self._verify_publish_result(driver, text)
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
            target = driver.execute_script(
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

                    const promptMarkers = [
                        'bạn đang nghĩ gì',
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

                    if (!candidates.length) return null;
                    return candidates[0].el.closest("div[role='button'], button, ytd-backstage-post-renderer") || candidates[0].el;
                """
            )
            if not target:
                return False
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
            time.sleep(0.5)
            try:
                target.click()
            except Exception:
                driver.execute_script("arguments[0].click();", target)
            return True
        except Exception:
            return False

    def _set_text_in_active_composer(self, driver: webdriver.Firefox, text: str) -> None:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                editor = self._find_editor(driver, timeout=8)
                self._set_text(driver, editor, text)
                if self._editor_has_text(driver, text):
                    return
            except Exception as exc:
                last_error = exc

            self._click_community_prompt(driver)
            time.sleep(1)
            try:
                self._type_text_to_active_element(driver, text)
                if self._editor_has_text(driver, text):
                    return
            except Exception as exc:
                last_error = exc

            try:
                if self._set_text_by_dom_without_editor(driver, text):
                    time.sleep(1)
                    if self._editor_has_text(driver, text):
                        return
            except Exception as exc:
                last_error = exc

        if last_error:
            raise RuntimeError(f"YouTube Community editor did not accept the post text: {last_error}")
        raise RuntimeError("YouTube Community editor did not accept the post text.")

    def _find_editor(self, driver: webdriver.Firefox, timeout: int = 45) -> WebElement:
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
                    "textarea, ytcp-social-suggestions-textbox, yt-emoji-input, #contenteditable-root, [contenteditable='true'], div[role='textbox'], [aria-label*='Bạn đang nghĩ'], [aria-label*='What are you thinking']"
                )).filter(isEditor);
                return candidates.length ? candidates[candidates.length - 1] : null;
                """
            )
            return editor or False

        return WebDriverWait(driver, timeout).until(find)

    def _type_text_to_active_element(self, driver: webdriver.Firefox, text: str) -> None:
        active = driver.switch_to.active_element
        modifier_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        ActionChains(driver).key_down(modifier_key).send_keys("a").key_up(modifier_key).perform()
        active.send_keys(Keys.BACKSPACE)
        time.sleep(0.3)
        active.send_keys(text)
        time.sleep(1)

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

    def _set_text_by_dom_without_editor(
        self,
        driver: webdriver.Firefox,
        text: str,
    ) -> bool:
        return bool(
            driver.execute_script(
                """
                const value = arguments[0];
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
                const candidates = Array.from(document.querySelectorAll(
                    "textarea, ytcp-social-suggestions-textbox, yt-emoji-input, #contenteditable-root, [contenteditable='true'], div[role='textbox']"
                ))
                    .filter(isVisible)
                    .filter((el) => {
                        const text = textFor(el);
                        return !text.includes('tìm kiếm') && !text.includes('search');
                    });
                const el = candidates[candidates.length - 1] || document.activeElement;
                if (!el) return false;
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
                for (const eventName of ['beforeinput', 'input', 'change', 'keyup', 'blur']) {
                    el.dispatchEvent(new Event(eventName, {bubbles: true}));
                }
                return true;
                """,
                text,
            )
        )

    def _install_youtube_dom_helpers(self, driver: webdriver.Firefox) -> None:
        driver.execute_script(
            """
            window.__mpv2FindYouTubeCommunityRoots = function(sample) {
                sample = String(sample || '').toLowerCase();

                function textFor(el) {
                    return [
                        el.innerText || '',
                        el.textContent || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('placeholder') || ''
                    ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
                }

                function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 20 && rect.height > 12 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        Number(style.opacity || 1) > 0;
                }

                const rootSelectors = [
                    'ytd-backstage-post-renderer',
                    'ytd-backstage-post-thread-renderer',
                    'ytd-backstage-post-dialog-renderer',
                    'tp-yt-paper-dialog',
                    'yt-dialog',
                    '[role="dialog"]',
                    'form',
                    'div'
                ];

                return Array.from(document.querySelectorAll(rootSelectors.join(',')))
                    .filter(isVisible)
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        const text = textFor(el);
                        const area = rect.width * rect.height;
                        return {el, rect, text, area};
                    })
                    .filter((item) =>
                        item.area > 10000 &&
                        item.area < 900000 &&
                        sample &&
                        item.text.includes(sample)
                    )
                    .sort((a, b) => a.area - b.area);
            };
            """
        )

    def _attach_image(
        self,
        driver: webdriver.Firefox,
        image_path: str,
        text: str,
    ) -> None:
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")

        before_preview_count = self._image_preview_count(driver, text)
        if not self._click_image_button_in_composer(driver, text):
            self._try_click_button(driver, YOUTUBE_IMAGE_MARKERS, "Image", 15)
        time.sleep(2)
        target_input = self._find_community_image_file_input(driver, text)
        if not target_input:
            raise RuntimeError("Could not find YouTube Community image file input.")

        target_input.send_keys(os.path.abspath(image_path))
        if not self._wait_for_image_attachment(driver, text, before_preview_count):
            raise RuntimeError("YouTube Community image did not attach before publishing.")

    def _find_community_image_file_input(
        self,
        driver: webdriver.Firefox,
        text: str,
    ) -> WebElement | None:
        sample = text.strip()[:80]
        try:
            return driver.execute_script(
                """
                const sample = String(arguments[0] || '').toLowerCase();

                function isUsableImageInput(el) {
                    if (!el || String(el.type || '').toLowerCase() !== 'file') return false;
                    const accept = String(el.getAttribute('accept') || '').toLowerCase();
                    return !accept || accept.includes('image') || accept.includes('png') || accept.includes('jpeg') || accept.includes('jpg');
                }

                const roots = window.__mpv2FindYouTubeCommunityRoots
                    ? window.__mpv2FindYouTubeCommunityRoots(sample)
                    : [];
                for (const root of roots) {
                    const inputs = Array.from(root.el.querySelectorAll('input[type="file"]'))
                        .filter(isUsableImageInput);
                    if (inputs.length) return inputs[inputs.length - 1];
                }

                const allImageInputs = Array.from(document.querySelectorAll('input[type="file"]'))
                    .filter(isUsableImageInput);
                return allImageInputs.length ? allImageInputs[allImageInputs.length - 1] : null;
                """,
                sample,
            )
        except Exception:
            return None

    def _click_image_button_in_composer(
        self,
        driver: webdriver.Firefox,
        text: str,
    ) -> bool:
        sample = text.strip()[:80]
        try:
            return bool(
                driver.execute_script(
                    """
                    const sample = String(arguments[0] || '').toLowerCase();
                    const markers = ['hình ảnh', 'image', 'photo', 'thêm ảnh', 'add image'];

                    function textFor(el) {
                        return [
                            el.innerText || '',
                            el.textContent || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || ''
                        ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
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
                        const className = String(el.getAttribute('class') || '').toLowerCase();
                        return !el.disabled &&
                            el.getAttribute('disabled') === null &&
                            el.getAttribute('aria-disabled') !== 'true' &&
                            !className.includes('disabled') &&
                            !className.includes('disable') &&
                            style.pointerEvents !== 'none';
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
                        try { el.click(); } catch (error) {}
                        return true;
                    }

                    const roots = window.__mpv2FindYouTubeCommunityRoots
                        ? window.__mpv2FindYouTubeCommunityRoots(sample)
                        : [];
                    for (const root of roots) {
                        const buttons = Array.from(root.el.querySelectorAll(
                            'button, tp-yt-paper-button, ytcp-button, yt-button-shape button, div[role="button"], a[role="button"]'
                        ))
                            .filter(isVisible)
                            .filter(isEnabled)
                            .map((el) => {
                                const text = textFor(el);
                                const rect = el.getBoundingClientRect();
                                let score = 0;
                                if (markers.some((marker) => text === marker)) score += 1000;
                                if (markers.some((marker) => text.includes(marker))) score += 500;
                                if (text.includes('đăng') || text.includes('post')) score -= 900;
                                score += Math.round((rect.left - root.rect.left) / 10);
                                score += Math.round((rect.top - root.rect.top) / 10);
                                return {el, score};
                            })
                            .filter((item) => item.score >= 500)
                            .sort((a, b) => b.score - a.score);
                        if (buttons.length) return clickElement(buttons[0].el);
                    }
                    return false;
                    """,
                    sample,
                )
            )
        except Exception:
            return False

    def _image_preview_count(self, driver: webdriver.Firefox, text: str) -> int:
        try:
            return int(
                driver.execute_script(
                    """
                    const sample = String(arguments[0] || '').toLowerCase();
                    const roots = window.__mpv2FindYouTubeCommunityRoots
                        ? window.__mpv2FindYouTubeCommunityRoots(sample)
                        : [];
                    const root = roots[0]?.el || document;
                    const scopedCount = Array.from(root.querySelectorAll('img, video, canvas, ytd-thumbnail, yt-img-shadow'))
                        .filter((el) => {
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width > 40 && rect.height > 40 &&
                                style.display !== 'none' &&
                                style.visibility !== 'hidden' &&
                                Number(style.opacity || 1) > 0;
                        }).length;
                    const blobCount = Array.from(document.querySelectorAll('img[src^="blob:"], img[src^="data:"], video[src^="blob:"], canvas'))
                        .filter((el) => {
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width > 40 && rect.height > 40 &&
                                style.display !== 'none' &&
                                style.visibility !== 'hidden' &&
                                Number(style.opacity || 1) > 0;
                        }).length;
                    return Math.max(scopedCount, blobCount);
                    """,
                    text.strip()[:80],
                )
                or 0
            )
        except Exception:
            return 0

    def _wait_for_image_attachment(
        self,
        driver: webdriver.Firefox,
        text: str,
        before_preview_count: int,
    ) -> bool:
        deadline = time.time() + 75
        while time.time() < deadline:
            if self._image_preview_count(driver, text) > before_preview_count:
                return True
            time.sleep(2)
        return False

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

    def _click_publish_button(
        self,
        driver: webdriver.Firefox,
        text: str,
        timeout: int = 60,
    ) -> None:
        deadline = time.time() + timeout
        last_clicked = False
        while time.time() < deadline:
            if self._click_publish_button_in_composer(driver, text):
                last_clicked = True
                time.sleep(4)
                if not self._composer_is_open(driver, text):
                    return
                if self._click_visible_publish_button(driver):
                    time.sleep(4)
                    if not self._composer_is_open(driver, text):
                        return
            else:
                if self._click_visible_publish_button(driver):
                    last_clicked = True
                    time.sleep(4)
                    if not self._composer_is_open(driver, text):
                        return
                time.sleep(1)

        if last_clicked:
            return

        button = self._find_button(driver, YOUTUBE_PUBLISH_MARKERS, 10, prefer_bottom=True)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", button)

    def _click_visible_publish_button(self, driver: webdriver.Firefox) -> bool:
        try:
            return bool(
                driver.execute_script(
                    """
                    function textFor(el) {
                        return [
                            el.innerText || '',
                            el.textContent || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || ''
                        ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
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
                        const className = String(el.getAttribute('class') || '').toLowerCase();
                        return !el.disabled &&
                            el.getAttribute('disabled') === null &&
                            el.getAttribute('aria-disabled') !== 'true' &&
                            !className.includes('disabled') &&
                            !className.includes('disable') &&
                            style.pointerEvents !== 'none';
                    }

                    function clickElement(el) {
                        const rect = el.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        el.scrollIntoView({block: 'center'});
                        for (const eventName of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
                            el.dispatchEvent(new MouseEvent(eventName, {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: x,
                                clientY: y
                            }));
                        }
                        try { el.click(); } catch (error) {}
                        return true;
                    }

                    function luminance(color) {
                        const match = String(color || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/i);
                        if (!match) return 255;
                        return (Number(match[1]) + Number(match[2]) + Number(match[3])) / 3;
                    }

                    const candidates = Array.from(document.querySelectorAll(
                        'button, tp-yt-paper-button, ytcp-button, yt-button-shape button, div[role="button"], a[role="button"]'
                    ))
                        .filter(isVisible)
                        .filter(isEnabled)
                        .map((el) => {
                            const text = textFor(el);
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            let score = 0;
                            if (text === 'đăng' || text === 'post') score += 1000;
                            if (text.includes('đăng') || text.includes('post')) score += 400;
                            if (text.includes('hủy') || text.includes('cancel')) score -= 900;
                            if (text.includes('bài đăng của tôi') || text.includes('my posts')) score -= 900;
                            if (text.includes('tạo') || text.includes('create')) score -= 600;
                            if (text.includes('lên lịch') || text.includes('schedule')) score -= 250;
                            if (luminance(style.backgroundColor) < 90) score += 500;
                            score += Math.round(rect.left / 8);
                            score -= Math.round(rect.top / 20);
                            return {el, score};
                        })
                        .filter((item) => item.score >= 900)
                        .sort((a, b) => b.score - a.score);

                    return candidates.length ? clickElement(candidates[0].el) : false;
                    """
                )
            )
        except Exception:
            return False

    def _click_publish_button_in_composer(
        self,
        driver: webdriver.Firefox,
        text: str,
    ) -> bool:
        sample = text.strip()[:80]
        try:
            return bool(
                driver.execute_script(
                    """
                    const sample = String(arguments[0] || '').toLowerCase();

                    function textFor(el) {
                        return [
                            el.innerText || '',
                            el.textContent || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || ''
                        ].join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
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
                        const className = String(el.getAttribute('class') || '').toLowerCase();
                        return !el.disabled &&
                            el.getAttribute('disabled') === null &&
                            el.getAttribute('aria-disabled') !== 'true' &&
                            !className.includes('disabled') &&
                            !className.includes('disable') &&
                            style.pointerEvents !== 'none';
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
                        try { el.click(); } catch (error) {}
                        return true;
                    }

                    function buttonScore(el, rootRect) {
                        const text = textFor(el);
                        const rect = el.getBoundingClientRect();
                        let score = 0;
                        if (text === 'đăng' || text === 'post') score += 1000;
                        if (text === 'xuất bản' || text === 'publish') score += 700;
                        if (text.includes('đăng') || text.includes('post')) score += 400;
                        if (text.includes('xuất bản') || text.includes('publish')) score += 300;
                        if (text.includes('bài đăng của tôi') || text.includes('my posts')) score -= 900;
                        if (text.includes('tạo') || text.includes('create')) score -= 400;
                        if (text.includes('lên lịch') || text.includes('schedule')) score -= 250;
                        score += Math.round((rect.left - rootRect.left) / 8);
                        score += Math.round((rect.top - rootRect.top) / 8);
                        return score;
                    }

                    const rootSelectors = [
                        'ytd-backstage-post-renderer',
                        'ytd-backstage-post-thread-renderer',
                        'ytd-backstage-post-dialog-renderer',
                        'tp-yt-paper-dialog',
                        'yt-dialog',
                        '[role="dialog"]',
                        'form',
                        'div'
                    ];
                    const roots = Array.from(document.querySelectorAll(rootSelectors.join(',')))
                        .filter(isVisible)
                        .map((el) => {
                            const rect = el.getBoundingClientRect();
                            const text = textFor(el);
                            const area = rect.width * rect.height;
                            return {el, rect, text, area};
                        })
                        .filter((item) =>
                            item.area > 10000 &&
                            item.area < 900000 &&
                            sample &&
                            item.text.includes(sample)
                        )
                        .sort((a, b) => a.area - b.area);

                    for (const root of roots) {
                        const buttons = Array.from(root.el.querySelectorAll(
                            'button, tp-yt-paper-button, ytcp-button, yt-button-shape button, div[role="button"], a[role="button"]'
                        ))
                            .filter(isVisible)
                            .filter(isEnabled)
                            .map((el) => ({el, score: buttonScore(el, root.rect)}))
                            .filter((item) => item.score >= 400)
                            .sort((a, b) => b.score - a.score);

                        if (buttons.length) return clickElement(buttons[0].el);
                    }

                    return false;
                    """,
                    sample,
                )
            )
        except Exception:
            return False

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

    def _verify_publish_result(self, driver: webdriver.Firefox, text: str = "") -> dict:
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

        if self._composer_is_open(driver, text):
            return {"success": False, "reason": "composer_still_open_after_click"}

        return {"success": True, "reason": "composer_closed_no_visible_error"}

    def _composer_is_open(self, driver: webdriver.Firefox, text: str = "") -> bool:
        try:
            return bool(
                driver.execute_script(
                    """
                    const sample = String(arguments[0] || '').toLowerCase();
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
                    if (!sample) {
                        const editors = Array.from(document.querySelectorAll(
                            "textarea, ytcp-social-suggestions-textbox, [contenteditable='true'], div[role='textbox']"
                        )).filter(isVisible);
                        return editors.length > 0;
                    }
                    const roots = Array.from(document.querySelectorAll(
                        "ytd-backstage-post-renderer, ytd-backstage-post-dialog-renderer, tp-yt-paper-dialog, yt-dialog, [role='dialog'], form, div"
                    ))
                        .filter(isVisible)
                        .filter((el) => {
                            const rect = el.getBoundingClientRect();
                            const area = rect.width * rect.height;
                            return area > 10000 &&
                                area < 900000 &&
                                textFor(el).includes(sample);
                        });
                    return roots.some((root) => Array.from(root.querySelectorAll(
                        "textarea, ytcp-social-suggestions-textbox, [contenteditable='true'], div[role='textbox']"
                    )).some(isVisible));
                    """,
                    text.strip()[:80],
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
