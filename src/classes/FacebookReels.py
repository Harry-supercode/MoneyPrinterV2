import os
import platform
import subprocess
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

from status import info, success, warning
# from src.status import info, success, warning


FACEBOOK_CAPTION_XPATHS = [
    (
        "//div[@role='textbox' and @contenteditable='true' and "
        "(contains(@aria-label, 'Describe') or "
        "contains(@aria-label, 'description') or "
        "contains(@aria-label, 'caption') or "
        "contains(@aria-label, 'Mô tả') or "
        "contains(@aria-label, 'Chú thích'))]"
    ),
    (
        "//textarea[contains(@aria-label, 'Describe') or "
        "contains(@aria-label, 'description') or "
        "contains(@aria-label, 'caption') or "
        "contains(@aria-label, 'Mô tả') or "
        "contains(@aria-label, 'Chú thích')]"
    ),
    "//div[@role='textbox' and @contenteditable='true']",
    "//*[@data-lexical-editor='true']",
    "//div[@contenteditable='true']",
    "//textarea",
]

FACEBOOK_CAPTION_MARKERS = [
    "describe your reel",
    "write a caption",
    "add a description",
    "say something about",
    "caption",
    "description",
    "mô tả",
    "chú thích",
    "viết chú thích",
    "bạn đang nghĩ gì",
]

FACEBOOK_NEGATIVE_INPUT_MARKERS = [
    "search",
    "tìm kiếm",
    "comment",
    "bình luận",
]


class FacebookReels:
    def __init__(self, fp_profile_path: str):
        self.fp_profile_path = fp_profile_path

        if not os.path.isdir(self.fp_profile_path):
            raise ValueError(f"Firefox profile path does not exist: {self.fp_profile_path}")

        self._assert_firefox_profile_available()

        self.options = Options()
        self.options.profile = self.fp_profile_path

        self.service = Service(GeckoDriverManager().install())
        self.browser = webdriver.Firefox(service=self.service, options=self.options)

    def _assert_firefox_profile_available(self) -> None:
        lock_path = os.path.join(self.fp_profile_path, ".parentlock")
        if not os.path.exists(lock_path):
            return

        active_process = self._find_firefox_process_using_profile()
        if not active_process:
            warning(
                f"Found stale Firefox profile lock, but no active Firefox process: {lock_path}"
            )
            return

        raise RuntimeError(
            "Firefox profile is currently in use. Close all Firefox windows that use "
            f"this profile before uploading to Facebook Reels: {self.fp_profile_path}. "
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

    @staticmethod
    def _clean_caption(caption: str) -> str:
        return " ".join(str(caption).split())[:2000]

    @staticmethod
    def _contains_any_marker(text: str, markers: list[str]) -> bool:
        normalized_text = str(text).lower()
        return any(marker in normalized_text for marker in markers)

    def _find_caption_box(self, driver: webdriver.Firefox) -> WebElement:
        def find_visible_caption_box(current_driver: webdriver.Firefox):
            candidate = self._find_caption_box_by_js(current_driver)
            if candidate:
                return candidate

            for xpath in FACEBOOK_CAPTION_XPATHS:
                elements = current_driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        descriptor = " ".join(
                            [
                                element.get_attribute("aria-label") or "",
                                element.get_attribute("placeholder") or "",
                                element.text or "",
                            ]
                        )
                        if self._contains_any_marker(descriptor, FACEBOOK_NEGATIVE_INPUT_MARKERS):
                            continue

                        if element.is_displayed() and element.is_enabled():
                            return element
                    except Exception:
                        continue

            self._activate_caption_placeholder(current_driver)
            active_element = current_driver.switch_to.active_element
            if self._looks_like_caption_box(active_element):
                return active_element

            return False

        return WebDriverWait(driver, 30).until(find_visible_caption_box)

    def _find_caption_box_by_js(self, driver: webdriver.Firefox) -> WebElement | None:
        return driver.execute_script(
            """
            const markers = arguments[0];
            const negativeMarkers = arguments[1];

            function textFor(el) {
                return [
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('placeholder') || '',
                    el.getAttribute('data-testid') || '',
                    el.innerText || '',
                    el.textContent || ''
                ].join(' ').toLowerCase();
            }

            function containsAny(text, values) {
                return values.some((value) => text.includes(value));
            }

            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return (
                    rect.width > 20 &&
                    rect.height > 12 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0
                );
            }

            const candidates = Array.from(document.querySelectorAll(
                "textarea, input[type='text'], [contenteditable='true'], [role='textbox'], [data-lexical-editor='true']"
            ));

            const scored = candidates
                .filter((el) => isVisible(el))
                .map((el) => {
                    const text = textFor(el);
                    let score = 0;
                    if (containsAny(text, negativeMarkers)) score -= 500;
                    if (containsAny(text, markers)) score += 300;
                    if (el.tagName === 'TEXTAREA') score += 120;
                    if (el.getAttribute('role') === 'textbox') score += 80;
                    if (el.getAttribute('contenteditable') === 'true') score += 60;
                    if (el.getAttribute('data-lexical-editor') === 'true') score += 60;
                    const rect = el.getBoundingClientRect();
                    score += Math.min(rect.width * rect.height / 1000, 80);
                    return {el, score};
                })
                .filter((item) => item.score > 0)
                .sort((a, b) => b.score - a.score);

            return scored.length ? scored[0].el : null;
            """,
            FACEBOOK_CAPTION_MARKERS,
            FACEBOOK_NEGATIVE_INPUT_MARKERS,
        )

    def _activate_caption_placeholder(self, driver: webdriver.Firefox) -> None:
        driver.execute_script(
            """
            const markers = arguments[0];

            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return (
                    rect.width > 20 &&
                    rect.height > 12 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0
                );
            }

            const elements = Array.from(document.querySelectorAll('span, div, label'));
            const placeholder = elements.find((el) => {
                const text = (el.innerText || el.textContent || '').toLowerCase();
                return isVisible(el) && markers.some((marker) => text.includes(marker));
            });

            if (placeholder) {
                placeholder.scrollIntoView({block: 'center'});
                placeholder.click();
            }
            """,
            FACEBOOK_CAPTION_MARKERS,
        )

    def _looks_like_caption_box(self, element: WebElement) -> bool:
        try:
            descriptor = " ".join(
                [
                    element.get_attribute("aria-label") or "",
                    element.get_attribute("placeholder") or "",
                    element.get_attribute("role") or "",
                    element.get_attribute("contenteditable") or "",
                    element.tag_name or "",
                ]
            )
            if self._contains_any_marker(descriptor, FACEBOOK_NEGATIVE_INPUT_MARKERS):
                return False
            return (
                element.is_displayed()
                and element.is_enabled()
                and (
                    element.tag_name in {"textarea", "input"}
                    or element.get_attribute("contenteditable") == "true"
                    or element.get_attribute("role") == "textbox"
                )
            )
        except Exception:
            return False

    def _set_caption(self, driver: webdriver.Firefox, caption: str) -> None:
        clean_caption = self._clean_caption(caption)
        if not clean_caption:
            return

        caption_box = self._find_caption_box(driver)
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            caption_box,
        )
        time.sleep(1)
        caption_box.click()
        time.sleep(0.5)

        self._clear_caption_box(driver, caption_box)
        if self._paste_caption_from_clipboard(driver, clean_caption):
            time.sleep(1)
            if self._caption_text_was_entered(driver, caption_box, clean_caption):
                return

        self._set_caption_with_js(driver, caption_box, clean_caption)
        time.sleep(1)
        if self._caption_text_was_entered(driver, caption_box, clean_caption):
            return

        caption_box.click()
        caption_box.send_keys(clean_caption)
        time.sleep(1)
        if not self._caption_text_was_entered(driver, caption_box, clean_caption):
            raise RuntimeError("Facebook caption box accepted only partial text.")

    def _clear_caption_box(self, driver: webdriver.Firefox, caption_box: WebElement) -> None:
        caption_box.click()
        modifier_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        ActionChains(driver).key_down(modifier_key).send_keys("a").key_up(modifier_key).perform()
        time.sleep(0.3)
        caption_box.send_keys(Keys.BACKSPACE)
        time.sleep(0.3)

    def _paste_caption_from_clipboard(self, driver: webdriver.Firefox, caption: str) -> bool:
        previous_clipboard = self._read_clipboard_text()
        if not self._write_clipboard_text(caption):
            return False

        try:
            modifier_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
            ActionChains(driver).key_down(modifier_key).send_keys("v").key_up(modifier_key).perform()
            return True
        finally:
            if previous_clipboard is not None:
                self._write_clipboard_text(previous_clipboard)

    def _read_clipboard_text(self) -> str | None:
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["pbpaste"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return result.stdout
        except Exception:
            return None

        return None

    def _write_clipboard_text(self, text: str) -> bool:
        try:
            if platform.system() == "Darwin":
                subprocess.run(
                    ["pbcopy"],
                    input=text,
                    check=True,
                    text=True,
                )
                return True
        except Exception as exc:
            warning(f"Could not use system clipboard for Facebook caption: {exc}")
            return False

        return False

    def _set_caption_with_js(
        self,
        driver: webdriver.Firefox,
        caption_box: WebElement,
        caption: str,
    ) -> None:
        driver.execute_script(
            """
            const el = arguments[0];
            const value = arguments[1];
            el.focus();
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                el.value = value;
            } else {
                el.textContent = value;
            }
            el.dispatchEvent(new InputEvent('beforeinput', {
                bubbles: true,
                inputType: 'insertText',
                data: value
            }));
            el.dispatchEvent(new InputEvent('input', {
                bubbles: true,
                inputType: 'insertText',
                data: value
            }));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            caption_box,
            caption,
        )

    def _caption_text_was_entered(
        self,
        driver: webdriver.Firefox,
        caption_box: WebElement,
        caption: str,
    ) -> bool:
        entered_text = driver.execute_script(
            """
            const el = arguments[0];
            return (el.value || el.innerText || el.textContent || '').trim();
            """,
            caption_box,
        )
        normalized_entered_text = self._clean_caption(entered_text)
        normalized_caption = self._clean_caption(caption)

        if normalized_caption and normalized_entered_text == normalized_caption:
            return True

        if len(normalized_entered_text) <= 1 and len(normalized_caption) > 1:
            warning(
                "Facebook caption input only contains "
                f"{repr(normalized_entered_text)} after entry attempt."
            )

        return False

    def _try_set_caption(self, driver: webdriver.Firefox, caption: str, stage: str) -> bool:
        if not caption:
            return True

        info(f" => Setting Facebook Reel caption ({stage})...")
        try:
            self._set_caption(driver, caption)
            time.sleep(2)
            success(f" => Set Facebook Reel caption ({stage}).")
            return True
        except Exception as e:
            warning(f"Could not set Facebook caption ({stage}): {e}")
            self._log_caption_candidates(driver)
            return False

    def _log_caption_candidates(self, driver: webdriver.Firefox) -> None:
        try:
            candidates = driver.execute_script(
                """
                return Array.from(document.querySelectorAll(
                    "textarea, input[type='text'], [contenteditable='true'], [role='textbox'], [data-lexical-editor='true']"
                )).slice(0, 12).map((el) => {
                    const rect = el.getBoundingClientRect();
                    return {
                        tag: el.tagName,
                        role: el.getAttribute('role') || '',
                        contenteditable: el.getAttribute('contenteditable') || '',
                        aria: el.getAttribute('aria-label') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        text: (el.innerText || el.textContent || '').slice(0, 80),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                    };
                });
                """
            )
            warning(f"Facebook caption candidates: {candidates}")
        except Exception as exc:
            warning(f"Could not inspect Facebook caption candidates: {exc}")

    def upload_profile_reel(self, video_path: str, caption: str = "") -> bool:
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        driver = self.browser

        try:
            info(" => Opening Facebook Reels create page...")
            driver.get("https://www.facebook.com/reels/create")
            time.sleep(10)

            info(" => Uploading Facebook Reel video...")
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")

            if not file_inputs:
                raise Exception("Could not find Facebook file input")

            file_inputs[0].send_keys(os.path.abspath(video_path))
            time.sleep(20)

            info(" => Clicking Next button...")
            next_buttons = driver.find_elements(
                By.XPATH,
                "//div[@role='button' and (.//span[contains(text(), 'Tiếp')] or .//span[contains(text(), 'Next')])]"
            )

            if not next_buttons:
                raise Exception("Could not find Next button")

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_buttons[-1])
            time.sleep(1)
            driver.execute_script("arguments[0].click();", next_buttons[-1])
            time.sleep(10)

            caption_set = False
            if caption:
                caption_set = self._try_set_caption(driver, caption, "after first Next")

            info(" => Clicking Next button again if available...")

            next_buttons = driver.find_elements(
                By.XPATH,
                "//div[@role='button' and (.//span[contains(text(), 'Tiếp')] or .//span[contains(text(), 'Next')])]"
            )

            if next_buttons:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_buttons[-1])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_buttons[-1])
                time.sleep(10)

            if caption and not caption_set:
                self._try_set_caption(driver, caption, "after final Next")

            info(" => Looking for Share/Publish button...")
            publish_buttons = driver.find_elements(
                By.XPATH,
                "//div[@role='button' and ("
                ".//span[contains(text(), 'Chia sẻ')] or "
                ".//span[contains(text(), 'Đăng')] or "
                ".//span[contains(text(), 'Share')] or "
                ".//span[contains(text(), 'Publish')]"
                ")]"
            )

            if not publish_buttons:
                all_buttons = driver.find_elements(By.XPATH, "//div[@role='button']")
                # print("===== FACEBOOK BUTTONS =====")
                # for i, btn in enumerate(all_buttons):
                #     try:
                #         print(i, repr(btn.text), repr(btn.get_attribute("aria-label")))
                #     except Exception:
                #         pass
                # print("============================")
                raise Exception("Could not find Share/Publish button")

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_buttons[-1])
            time.sleep(1)
            driver.execute_script("arguments[0].click();", publish_buttons[-1])
            time.sleep(20)

            success(" => Uploaded Facebook Profile Reel.")
            driver.quit()
            return True

        except Exception:
            traceback.print_exc()
            warning(" => Failed to upload Facebook Profile Reel.")

            try:
                driver.quit()
            except Exception:
                pass

            return False
