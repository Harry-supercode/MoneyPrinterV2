import json
import os
import re
import time
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

from config import get_firefox_binary_path
from status import info, warning
from .DubSourceCheckpoint import is_source_processed


class DubBrowserDiscovery:
    source_name = "browser"
    search_url_template = ""
    allowed_domains: tuple[str, ...] = ()
    url_markers: tuple[str, ...] = ()

    def __init__(self, config: dict) -> None:
        self.config = config

    def discover(self, keyword: str, run_dir: str = "") -> list[dict]:
        url = self._discovery_url(keyword)
        max_candidates = int(self.config.get("max_candidates", 12))
        wait_seconds = int(self.config.get("discovery_wait_seconds", 12))
        login_wait_seconds = int(self.config.get("discovery_login_wait_seconds", 0))

        info(f" => Discovering {self.source_name} candidates for keyword: {keyword}")
        driver = self._open_browser()

        try:
            driver.get(url)
            time.sleep(wait_seconds)
            candidates, raw_links = self._extract_candidates(driver, keyword, max_candidates)
            if (
                not candidates
                and login_wait_seconds > 0
                and not bool(self.config.get("discovery_headless", True))
            ):
                info(
                    " => No candidates yet. Keeping Firefox open "
                    f"{login_wait_seconds}s for login/captcha, then retrying scan..."
                )
                time.sleep(login_wait_seconds)
                candidates, raw_links = self._extract_candidates(driver, keyword, max_candidates)

            if run_dir:
                self._write_debug_artifacts(driver, run_dir, keyword, url, raw_links, candidates)
            if candidates:
                info(f" => Found {len(candidates)} {self.source_name} candidates.")
            else:
                warning(f"No {self.source_name} candidates found.")
            return candidates
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _open_browser(self) -> webdriver.Firefox:
        options = Options()
        firefox_binary_path = get_firefox_binary_path()
        if firefox_binary_path:
            options.binary_location = firefox_binary_path

        if bool(self.config.get("discovery_headless", True)):
            options.add_argument("--headless")

        profile_path = str(self.config.get("browser_profile", "")).strip()
        if profile_path:
            if not os.path.isdir(profile_path):
                raise ValueError(f"dub_pipeline.browser_profile does not exist: {profile_path}")
            options.profile = profile_path

        service = Service(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=options)

    def _discovery_url(self, keyword: str) -> str:
        return self.search_url_template.format(keyword=quote_plus(keyword))

    def _extract_candidates(
        self,
        driver: webdriver.Firefox,
        keyword: str,
        max_candidates: int,
    ) -> tuple[list[dict], list[dict]]:
        raw_links = driver.execute_script(
            """
            const values = [];
            const push = (url, text = '', title = '') => {
                if (!url) return;
                values.push({href: String(url), text: String(text || '').trim(), title: String(title || '').trim()});
            };

            for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                const card = a.closest('[class*=note], [class*=card], [class*=item], section, article, div');
                const cardText = card ? card.innerText : '';
                push(
                    a.href,
                    cardText || a.innerText || a.getAttribute('aria-label') || '',
                    a.getAttribute('title') || ''
                );
            }

            const html = document.documentElement.innerHTML;
            const patterns = [
                /https?:\\/\\/[^"'\\s<>]+/g,
                /\\/explore\\/[A-Za-z0-9_-]+/g,
                /\\/video\\/[A-Za-z0-9_-]+/g,
                /\\/share\\/video\\/[A-Za-z0-9_-]+/g
            ];
            for (const pattern of patterns) {
                for (const match of html.matchAll(pattern)) {
                    let value = match[0].replaceAll('\\\\u002F', '/').replaceAll('&amp;', '&');
                    if (value.startsWith('/')) value = location.origin + value;
                    push(value);
                }
            }

            return values;
            """
        )

        candidates_by_note_id = {}
        for item in raw_links:
            href = str(item.get("href", "")).strip()
            if not href or "/404" in href:
                continue

            if not self._looks_like_video_url(href):
                continue

            if is_source_processed(href):
                continue

            engagement_score = self._parse_engagement_score(
                " ".join(
                    [
                        str(item.get("title", "")),
                        str(item.get("text", "")),
                    ]
                )
            )

            note_id = self._note_id_from_url(href) or href
            candidate = {
                "source": self.source_name,
                "keyword": keyword,
                "url": href,
                "title": str(item.get("title") or item.get("text") or "").strip(),
                "engagement_score": engagement_score,
                "selected": False,
            }
            current = candidates_by_note_id.get(note_id)
            if current is None or self._candidate_rank(candidate) > self._candidate_rank(current):
                candidates_by_note_id[note_id] = candidate

        candidates = sorted(
            candidates_by_note_id.values(),
            key=lambda candidate: candidate.get("engagement_score", 0),
            reverse=True,
        )

        return candidates[:max_candidates], raw_links

    @staticmethod
    def _note_id_from_url(url: str) -> str:
        match = re.search(r"/(?:explore|search_result|discovery/item)/([A-Za-z0-9_-]+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _candidate_rank(candidate: dict) -> tuple[int, float, int]:
        url = str(candidate.get("url", ""))
        token_score = 2 if "xsec_token=" in url else 0
        route_score = 1 if "/search_result/" in url else 0
        title_score = 1 if str(candidate.get("title", "")).strip() else 0
        return (
            token_score + route_score + title_score,
            float(candidate.get("engagement_score", 0)),
            len(url),
        )

    @staticmethod
    def _parse_engagement_score(text: str) -> float:
        score = 0.0
        for raw_number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([万億亿kKmM]?)", text):
            value = float(raw_number)
            if unit == "万":
                value *= 10_000
            elif unit in {"億", "亿"}:
                value *= 100_000_000
            elif unit in {"k", "K"}:
                value *= 1_000
            elif unit in {"m", "M"}:
                value *= 1_000_000
            score = max(score, value)
        return score

    def _write_debug_artifacts(
        self,
        driver: webdriver.Firefox,
        run_dir: str,
        keyword: str,
        search_url: str,
        raw_links: list[dict],
        candidates: list[dict],
    ) -> None:
        payload = {
            "source": self.source_name,
            "keyword": keyword,
            "search_url": search_url,
            "current_url": driver.current_url,
            "title": driver.title,
            "raw_link_count": len(raw_links),
            "candidate_count": len(candidates),
            "raw_links": raw_links[:200],
            "candidates": candidates,
        }

        with open(
            os.path.join(run_dir, f"discovery_{self.source_name}_links.json"),
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        with open(
            os.path.join(run_dir, f"discovery_{self.source_name}.html"),
            "w",
            encoding="utf-8",
        ) as file:
            file.write(driver.page_source)

        try:
            driver.save_screenshot(os.path.join(run_dir, f"discovery_{self.source_name}.png"))
        except Exception:
            pass

    def _looks_like_video_url(self, url: str) -> bool:
        normalized = url.lower()
        if self.allowed_domains and not any(domain in normalized for domain in self.allowed_domains):
            return False

        if not self.url_markers:
            return True

        return any(marker in normalized for marker in self.url_markers)
