import json
import os
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

from config import get_firefox_binary_path
from firefox_profile import apply_firefox_profile
from .DubFfmpeg import resolve_ffmpeg, resolve_ffprobe
from status import info, warning
from .DubSourceCheckpoint import mark_source_processed


class DubVideoDownloader:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.ffmpeg = resolve_ffmpeg(config)
        self.ffprobe = resolve_ffprobe(config)

    def download(self, run_dir: str, candidates: list[dict]) -> str:
        source_video_path = self.config.get("source_video_path", "")
        if source_video_path:
            if not os.path.exists(source_video_path):
                raise FileNotFoundError(f"dub_pipeline.source_video_path not found: {source_video_path}")

            target_path = os.path.join(run_dir, "source_video.mp4")
            shutil.copy2(source_video_path, target_path)
            metadata = {
                "source": "local_file",
                "source_video_path": os.path.abspath(source_video_path),
            }
            self._write_outputs(run_dir, candidates, metadata)
            return target_path

        return self._download_candidates_with_ytdlp(run_dir, candidates)

    def _download_candidates_with_ytdlp(self, run_dir: str, candidates: list[dict]) -> str:
        if not candidates:
            self._write_outputs(
                run_dir,
                [],
                {
                    "source": "discovered",
                    "download_method": "yt-dlp",
                    "error": "No discovered video candidates to download",
                },
            )
            raise RuntimeError("No discovered video candidates to download")

        ytdlp_command = self._ytdlp_command()
        if not ytdlp_command:
            raise RuntimeError(
                "yt-dlp is required for discovered source download. Install it with "
                "`brew install yt-dlp` or `pip install yt-dlp`."
            )

        target_path = os.path.join(run_dir, "source_video.mp4")
        attempts = []
        ordered_candidates = sorted(
            candidates,
            key=lambda candidate: float(candidate.get("engagement_score", 0)),
            reverse=True,
        )
        if ordered_candidates:
            top_candidate = ordered_candidates[0]
            info(
                " => Top source candidate before download: "
                f"score={top_candidate.get('engagement_score', 0)} "
                f"url={top_candidate.get('url', '')}"
            )

        for candidate in ordered_candidates:
            downloaded_path = self._try_download_candidate_with_ytdlp(
                candidate,
                target_path,
                ytdlp_command,
                attempts,
            )
            candidate_url = candidate.get("url", "")
            if downloaded_path:
                candidate["selected"] = True
                mark_source_processed(candidate_url, target_path)
                metadata = {
                    "source": candidate.get("source", ""),
                    "source_url": candidate_url,
                    "source_title": candidate.get("title", ""),
                    "download_method": "yt-dlp",
                    "download_attempts": attempts,
                }
                self._write_outputs(run_dir, candidates, metadata)
                return downloaded_path

            browser_attempt = self._download_with_browser_capture(
                candidate,
                target_path,
                run_dir,
            )
            attempts.append(browser_attempt)
            if browser_attempt.get("success") and os.path.exists(target_path):
                candidate["selected"] = True
                mark_source_processed(candidate_url, target_path)
                metadata = {
                    "source": candidate.get("source", ""),
                    "source_url": candidate_url,
                    "source_title": candidate.get("title", ""),
                    "download_method": "browser_capture",
                    "download_attempts": attempts,
                }
                self._write_outputs(run_dir, candidates, metadata)
                return target_path

        fallback_candidates = self._fallback_source_candidates(ordered_candidates)
        if fallback_candidates:
            warning(
                "All discovered source candidates failed. Trying configured "
                "dub_pipeline.fallback_source_urls."
            )
        for candidate in fallback_candidates:
            downloaded_path = self._try_download_candidate_with_ytdlp(
                candidate,
                target_path,
                ytdlp_command,
                attempts,
            )
            candidate_url = candidate.get("url", "")
            if downloaded_path:
                candidate["selected"] = True
                mark_source_processed(candidate_url, target_path)
                all_candidates = ordered_candidates + fallback_candidates
                metadata = {
                    "source": candidate.get("source", ""),
                    "source_url": candidate_url,
                    "source_title": candidate.get("title", ""),
                    "download_method": "fallback_source_url",
                    "download_attempts": attempts,
                }
                self._write_outputs(run_dir, all_candidates, metadata)
                return downloaded_path

        self._write_outputs(
            run_dir,
            ordered_candidates + fallback_candidates,
            {
                "source": "discovered",
                "download_method": "yt-dlp",
                "download_attempts": attempts,
            },
        )
        raise RuntimeError("All discovered source download candidates failed")

    def _try_download_candidate_with_ytdlp(
        self,
        candidate: dict,
        target_path: str,
        ytdlp_command: list[str],
        attempts: list[dict],
    ) -> str:
        candidate_url = candidate.get("url", "")
        if not candidate_url:
            return ""
        if "/404" in candidate_url:
            warning(f"Skipping invalid Rednote 404 candidate URL: {candidate_url}")
            return ""

        info(f" => Downloading source candidate with yt-dlp: {candidate_url}")
        command = [
            *ytdlp_command,
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-f",
            "bv*+ba/b",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
            "--referer",
            self._referer_for_url(candidate_url),
            "-o",
            target_path,
            candidate_url,
        ]
        browser_profile = str(self.config.get("browser_profile", "")).strip()
        if browser_profile:
            insert_at = len(ytdlp_command)
            command[insert_at:insert_at] = [
                "--cookies-from-browser",
                f"firefox:{browser_profile}",
            ]

        result = subprocess.run(command, capture_output=True, text=True)
        attempt = {
            "candidate": candidate,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        }
        attempts.append(attempt)

        if result.returncode == 0 and os.path.exists(target_path):
            if not self._is_valid_video(target_path):
                warning("yt-dlp output is not a valid video. Trying next method.")
                self._remove_file(target_path)
                attempt["invalid_video"] = True
                return ""
            return target_path

        if result.returncode == 0 and os.path.exists(target_path):
            self._remove_file(target_path)

        if result.returncode != 0:
            warning(f"yt-dlp failed for candidate: {candidate_url}")
        return ""

    def _fallback_source_candidates(self, existing_candidates: list[dict]) -> list[dict]:
        existing_urls = {
            str(candidate.get("url", "")).strip()
            for candidate in existing_candidates
            if str(candidate.get("url", "")).strip()
        }
        fallback_urls = self.config.get("fallback_source_urls", [])
        if not isinstance(fallback_urls, list):
            return []

        candidates = []
        for index, raw_url in enumerate(fallback_urls, start=1):
            url = str(raw_url).strip()
            if not url or url in existing_urls:
                continue
            candidates.append(
                {
                    "source": "fallback_source_url",
                    "title": f"Configured fallback source {index}",
                    "url": url,
                    "engagement_score": 0,
                }
            )
        return candidates

    @staticmethod
    def _referer_for_url(url: str) -> str:
        hostname = urlparse(url).hostname or ""
        if "rednote.com" in hostname or "xiaohongshu.com" in hostname:
            return "https://www.rednote.com/"
        if "douyin.com" in hostname:
            return "https://www.douyin.com/"
        return f"{urlparse(url).scheme or 'https'}://{hostname}/" if hostname else "https://www.google.com/"

    def _ytdlp_command(self) -> list[str]:
        try:
            import yt_dlp  # noqa: F401

            return [sys.executable, "-m", "yt_dlp"]
        except Exception:
            pass

        binary_path = shutil.which("yt-dlp")
        if binary_path:
            return [binary_path]

        return []

    def _download_with_browser_capture(
        self,
        candidate: dict,
        target_path: str,
        run_dir: str,
    ) -> dict:
        candidate_url = candidate.get("url", "")
        if not candidate_url:
            return {"method": "browser_capture", "success": False, "error": "empty candidate url"}
        if "/404" in candidate_url:
            return {
                "method": "browser_capture",
                "success": False,
                "error": f"invalid 404 candidate url: {candidate_url}",
            }

        info(f" => Trying browser capture download: {candidate_url}")
        try:
            driver = self._open_browser()
        except Exception as exc:
            warning(f"Browser capture could not open Firefox: {exc}")
            return {
                "method": "browser_capture",
                "success": False,
                "candidate": candidate,
                "error": f"Could not open Firefox: {exc}",
            }

        try:
            driver.get(candidate_url)
            wait_seconds = int(self.config.get("download_capture_wait_seconds", 18))
            time.sleep(max(3, min(wait_seconds, 90)))
            if "/404" in driver.current_url:
                return {
                    "method": "browser_capture",
                    "success": False,
                    "candidate": candidate,
                    "error": f"Rednote redirected candidate to 404: {driver.current_url}",
                }
            video_urls = self._extract_video_urls(driver)
            if not video_urls and not bool(self.config.get("discovery_headless", True)):
                manual_wait_seconds = int(self.config.get("download_manual_wait_seconds", 60))
                info(
                    " => No media resource found yet. Click/play the Rednote video "
                    f"within {manual_wait_seconds}s, then capture will retry..."
                )
                time.sleep(max(5, min(manual_wait_seconds, 180)))
                video_urls = self._extract_video_urls(driver)

            debug_path = os.path.join(run_dir, "download_browser_capture.json")
            with open(debug_path, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "candidate_url": candidate_url,
                        "current_url": driver.current_url,
                        "title": driver.title,
                        "video_url_count": len(video_urls),
                        "video_urls": video_urls[:30],
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            cookies = self._cookie_header(driver)
            for video_url in video_urls:
                try:
                    if ".m3u8" in video_url:
                        self._download_hls_with_ffmpeg(video_url, target_path, cookies, candidate_url)
                    else:
                        self._download_direct_video(video_url, target_path, cookies, candidate_url)

                    if self._is_valid_video(target_path):
                        return {
                            "method": "browser_capture",
                            "success": True,
                            "candidate": candidate,
                            "video_url": self._safe_url_for_metadata(video_url),
                        }
                    self._remove_file(target_path)
                except Exception as exc:
                    self._remove_file(target_path)
                    warning(f"Browser capture video URL failed: {exc}")

            return {
                "method": "browser_capture",
                "success": False,
                "candidate": candidate,
                "error": "No downloadable video resource found",
                "video_url_count": len(video_urls),
            }
        except Exception as exc:
            return {
                "method": "browser_capture",
                "success": False,
                "candidate": candidate,
                "error": str(exc),
            }
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
            self._clear_stale_firefox_lock(profile_path)
            apply_firefox_profile(options, profile_path)

        service = Service(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=options)

    def _extract_video_urls(self, driver: webdriver.Firefox) -> list[str]:
        urls = driver.execute_script(
            """
            const urls = [];
            const push = (value) => {
                if (!value) return;
                const url = String(value).replaceAll('\\\\u002F', '/').replaceAll('&amp;', '&');
                urls.push(url);
            };

            for (const video of Array.from(document.querySelectorAll('video, source'))) {
                push(video.currentSrc);
                push(video.src);
                push(video.getAttribute('src'));
            }

            for (const item of performance.getEntriesByType('resource')) {
                push(item.name);
            }

            const html = document.documentElement.innerHTML;
            const patterns = [
                /https?:\\/\\/[^"'\\s<>]+?\\.mp4[^"'\\s<>]*/g,
                /https?:\\/\\/[^"'\\s<>]+?\\.m3u8[^"'\\s<>]*/g,
                /https?:\\/\\/[^"'\\s<>]+?(?:sns-video|sns-video-qc|sns-video-hw|video)[^"'\\s<>]+?\\.(?:mp4|m3u8)[^"'\\s<>]*/g
            ];
            for (const pattern of patterns) {
                for (const match of html.matchAll(pattern)) {
                    push(match[0]);
                }
            }

            return urls;
            """
        )

        normalized_urls = []
        seen_urls = set()
        for url in urls:
            cleaned_url = str(url).strip()
            if not cleaned_url or cleaned_url.startswith("blob:"):
                continue

            if not self._looks_like_media_url(cleaned_url):
                continue

            if cleaned_url in seen_urls:
                continue

            seen_urls.add(cleaned_url)
            normalized_urls.append(cleaned_url)

        return normalized_urls

    @staticmethod
    def _looks_like_media_url(url: str) -> bool:
        lowered = url.lower()
        if any(marker in lowered for marker in ["/api/", ".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".ico"]):
            return False
        return ".mp4" in lowered or ".m3u8" in lowered

    @staticmethod
    def _cookie_header(driver: webdriver.Firefox) -> str:
        return "; ".join(
            f"{cookie['name']}={cookie['value']}"
            for cookie in driver.get_cookies()
            if cookie.get("name") and cookie.get("value")
        )

    def _download_direct_video(
        self,
        video_url: str,
        target_path: str,
        cookies: str,
        referer: str,
    ) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
            "Referer": referer,
        }
        if cookies:
            headers["Cookie"] = cookies

        with requests.get(video_url, headers=headers, timeout=120, stream=True) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "video" not in content_type and "octet-stream" not in content_type and ".mp4" not in video_url.lower():
                raise RuntimeError(f"Unexpected content type for video download: {content_type}")
            with open(target_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)

    def _download_hls_with_ffmpeg(
        self,
        video_url: str,
        target_path: str,
        cookies: str,
        referer: str,
    ) -> None:
        headers = (
            "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0\r\n"
            f"Referer: {referer}\r\n"
        )
        if cookies:
            headers += f"Cookie: {cookies}\r\n"

        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-headers",
                headers,
                "-i",
                video_url,
                "-c",
                "copy",
                target_path,
            ],
            check=True,
        )

    @staticmethod
    def _safe_url_for_metadata(url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(query="[redacted]", fragment="").geturl()

    def _is_valid_video(self, video_path: str) -> bool:
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 100_000:
            return False

        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "video" in result.stdout

    @staticmethod
    def _clear_stale_firefox_lock(profile_path: str) -> None:
        lock_path = os.path.join(profile_path, ".parentlock")
        if not os.path.exists(lock_path):
            return

        try:
            result = subprocess.run(
                ["pgrep", "-fl", "Firefox|firefox|geckodriver"],
                capture_output=True,
                text=True,
            )
            active_process = result.stdout.strip()
        except Exception:
            active_process = ""

        if active_process:
            return

        try:
            os.remove(lock_path)
            warning(f"Removed stale Firefox profile lock: {lock_path}")
        except OSError as exc:
            warning(f"Could not remove stale Firefox profile lock {lock_path}: {exc}")

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def _write_outputs(self, run_dir: str, candidates: list[dict], metadata: dict) -> None:
        with open(os.path.join(run_dir, "candidates.json"), "w", encoding="utf-8") as file:
            json.dump(candidates, file, ensure_ascii=False, indent=2)

        with open(os.path.join(run_dir, "source_metadata.json"), "w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)
