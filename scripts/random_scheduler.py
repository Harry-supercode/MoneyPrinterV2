#!/usr/bin/env python3
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_ROOT = Path("/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2")
ROOT = Path(os.environ.get("MPV2_ROOT", DEFAULT_ROOT)).expanduser()
if not (ROOT / "config.json").exists():
    ROOT = Path(__file__).resolve().parents[1]
MP_DIR = ROOT / ".mp"
STATE_PATH = MP_DIR / "random_scheduler_state.json"
LOG_PATH = ROOT / "random_scheduler.log"


DEFAULT_CONFIG = {
    "enabled": True,
    "daily_job_limit": 6,
    "window_start": "08:30",
    "window_end": "22:30",
    "min_gap_minutes": 120,
    "tick_grace_minutes": 20,
    "override_platform_uploads": False,
    "jobs": [
        {"name": "youtube_short", "count": 3},
        {"name": "dub_pipeline", "count": 3},
        {"name": "social_post", "count": 0},
    ],
    "platform_limits": {
        "facebook_reels": 2,
        "tiktok": 2,
    },
    "launchers": {
        "youtube_short": str(ROOT / "scripts" / "run_youtube_short_job.sh"),
        "dub_pipeline": str(ROOT / "scripts" / "run_dub_pipeline_job.sh"),
        "social_post": str(ROOT / "scripts" / "run_social_post_job.sh"),
    },
    "launch_probe_seconds": 8,
}


JOB_HEALTH = {
    "youtube_short": {
        "lock": Path("/tmp/moneyprinterv2-youtube-short.lock"),
        "log": ROOT / "cron.log",
        "start_text": "START youtube_short",
        "process_pattern": "[s]rc/cron.py youtube",
    },
    "dub_pipeline": {
        "lock": Path("/tmp/moneyprinterv2-dub-pipeline.lock"),
        "log": ROOT / "dub_cron.log",
        "start_text": "START dub_pipeline",
        "process_pattern": "[s]rc/dub_cron.py",
    },
    "social_post": {
        "lock": Path("/tmp/moneyprinterv2-social-post.lock"),
        "log": ROOT / "social_posts.log",
        "start_text": "START social_post",
        "process_pattern": "[s]rc/social_post_cron.py",
    },
}


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")


def log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp()}] {message}\n")


def load_json(path: Path, default: dict) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else default
    except (OSError, ValueError, TypeError):
        return default


def load_config() -> dict:
    config_json = load_json(ROOT / "config.json", {})
    raw_config = config_json.get("random_scheduler", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    config = dict(DEFAULT_CONFIG)
    config.update({key: value for key, value in raw_config.items() if key in config})

    if not isinstance(config.get("jobs"), list):
        config["jobs"] = DEFAULT_CONFIG["jobs"]
    if not isinstance(config.get("platform_limits"), dict):
        config["platform_limits"] = DEFAULT_CONFIG["platform_limits"]
    if not isinstance(config.get("launchers"), dict):
        config["launchers"] = DEFAULT_CONFIG["launchers"]

    config["daily_job_limit"] = max(1, int(config.get("daily_job_limit", 6)))
    config["min_gap_minutes"] = max(30, int(config.get("min_gap_minutes", 120)))
    config["tick_grace_minutes"] = max(5, int(config.get("tick_grace_minutes", 20)))
    config["launch_probe_seconds"] = max(
        1, int(config.get("launch_probe_seconds", 8))
    )
    config["override_platform_uploads"] = bool(
        config.get("override_platform_uploads", False)
    )
    return config


def parse_time_for_today(value: str, today: datetime) -> datetime:
    hour, minute = [int(part) for part in str(value).split(":", 1)]
    return today.replace(hour=hour, minute=minute, second=0, microsecond=0)


def build_job_names(config: dict) -> list[str]:
    names = []
    for item in config["jobs"]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        try:
            count = int(item.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if name and count > 0:
            names.extend([name] * count)

    if not names:
        names = ["youtube_short"] * config["daily_job_limit"]

    random.shuffle(names)
    return names[: config["daily_job_limit"]]


def choose_times(config: dict, today: datetime, count: int) -> list[datetime]:
    start = parse_time_for_today(config["window_start"], today)
    end = parse_time_for_today(config["window_end"], today)
    current = datetime.now()
    if start.date() == current.date() and current > start:
        start = current.replace(second=0, microsecond=0) + timedelta(minutes=15)

    if end <= start:
        raise ValueError("random_scheduler.window_end must be after window_start")

    total_minutes = int((end - start).total_seconds() // 60)
    min_gap = config["min_gap_minutes"]

    for _ in range(2000):
        minutes = sorted(random.sample(range(total_minutes + 1), count))
        if all((b - a) >= min_gap for a, b in zip(minutes, minutes[1:])):
            return [start + timedelta(minutes=minute) for minute in minutes]

    spacing = total_minutes // max(count - 1, 1)
    if spacing < min_gap:
        log(
            "WARN random_scheduler window is tight for requested min gap; "
            f"using even spacing of {spacing} minutes"
        )
    return [start + timedelta(minutes=spacing * idx) for idx in range(count)]


def assign_platforms(slots: list[dict], config: dict) -> None:
    if not config.get("override_platform_uploads", False):
        return

    platform_limits = config["platform_limits"]
    try:
        facebook_limit = max(0, int(platform_limits.get("facebook_reels", 0)))
    except (TypeError, ValueError):
        facebook_limit = 0
    try:
        tiktok_limit = max(0, int(platform_limits.get("tiktok", 0)))
    except (TypeError, ValueError):
        tiktok_limit = 0

    platform_candidates = slots[:]
    random.shuffle(platform_candidates)
    for slot in platform_candidates[:facebook_limit]:
        slot["platforms"]["facebook_reels"] = True

    youtube_slots = [slot for slot in slots if slot["job"] == "youtube_short"]
    random.shuffle(youtube_slots)
    for slot in youtube_slots[:tiktok_limit]:
        slot["platforms"]["tiktok"] = True


def generate_schedule(config: dict, today: datetime) -> dict:
    jobs = build_job_names(config)
    times = choose_times(config, today, len(jobs))
    slots = []
    for idx, (run_at, job) in enumerate(zip(times, jobs), start=1):
        slots.append(
            {
                "id": f"{today.strftime('%Y%m%d')}-{idx:02d}",
                "run_at": run_at.strftime("%Y-%m-%d %H:%M:%S"),
                "job": job,
                "status": "pending",
                "platforms": {
                    "facebook_reels": False,
                    "tiktok": False,
                },
                "override_platform_uploads": bool(
                    config.get("override_platform_uploads", False)
                ),
            }
        )

    assign_platforms(slots, config)
    return {
        "date": today.strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "slots": slots,
    }


def load_or_create_state(config: dict) -> dict:
    MP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    state = load_json(STATE_PATH, {})
    if state.get("date") != today.strftime("%Y-%m-%d"):
        state = generate_schedule(config, today)
        save_state(state)
        if config.get("override_platform_uploads", False):
            pretty_slots = ", ".join(
                f"{slot['run_at'][11:16]}:{slot['job']}:"
                f"fb={int(slot['platforms']['facebook_reels'])}:"
                f"tt={int(slot['platforms']['tiktok'])}"
                for slot in state["slots"]
            )
        else:
            pretty_slots = ", ".join(
                f"{slot['run_at'][11:16]}:{slot['job']}:platforms=default"
                for slot in state["slots"]
            )
        log(f"Generated random schedule: {pretty_slots}")
    return state


def save_state(state: dict) -> None:
    MP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    tmp_path.replace(STATE_PATH)


def active_job_exists() -> bool:
    lock_paths = [
        Path("/tmp/moneyprinterv2-youtube-short.lock"),
        Path("/tmp/moneyprinterv2-dub-pipeline.lock"),
        Path("/tmp/moneyprinterv2-social-post.lock"),
    ]
    if any(path.exists() for path in lock_paths):
        return True

    checks = [
        ["pgrep", "-f", "[s]rc/cron.py youtube"],
        ["pgrep", "-f", "[s]rc/dub_cron.py"],
        ["pgrep", "-f", "[s]rc/social_post_cron.py"],
    ]
    for cmd in checks:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return True
    return False


def job_health_snapshot(job: str) -> dict:
    health = JOB_HEALTH.get(job, {})
    log_path = health.get("log")
    try:
        log_size = log_path.stat().st_size if log_path else 0
    except OSError:
        log_size = 0
    return {"log_size": log_size}


def log_contains_start_since(job: str, start_offset: int) -> bool:
    health = JOB_HEALTH.get(job, {})
    log_path = health.get("log")
    start_text = health.get("start_text")
    if not log_path or not start_text:
        return False

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as file:
            file.seek(start_offset)
            return start_text in file.read()
    except OSError:
        return False


def process_exists(pattern: str) -> bool:
    result = subprocess.run(
        ["pgrep", "-f", pattern],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def job_started(job: str, snapshot: dict) -> bool:
    health = JOB_HEALTH.get(job, {})
    lock_path = health.get("lock")
    process_pattern = health.get("process_pattern")

    if lock_path and lock_path.exists():
        return True
    if process_pattern and process_exists(str(process_pattern)):
        return True
    return log_contains_start_since(job, int(snapshot.get("log_size", 0)))


def build_env(slot: dict) -> dict:
    env = os.environ.copy()
    if not slot.get("override_platform_uploads", False):
        return env

    platforms = slot.get("platforms", {})
    facebook_enabled = "1" if platforms.get("facebook_reels") else "0"
    tiktok_enabled = "1" if platforms.get("tiktok") else "0"

    if slot["job"] == "youtube_short":
        env["MPV2_UPLOAD_FACEBOOK_REELS"] = facebook_enabled
        env["MPV2_UPLOAD_TIKTOK"] = tiktok_enabled
    elif slot["job"] == "dub_pipeline":
        env["MPV2_DUB_UPLOAD_YOUTUBE"] = "1"
        env["MPV2_DUB_UPLOAD_FACEBOOK_REELS"] = facebook_enabled
        env["MPV2_DUB_UPLOAD_TIKTOK"] = tiktok_enabled

    return env


def launch_slot(slot: dict, config: dict) -> bool:
    launcher = config["launchers"].get(slot["job"])
    if not launcher:
        slot["status"] = "failed"
        slot["error"] = f"No launcher configured for job: {slot['job']}"
        return False

    launcher_path = Path(launcher).expanduser()
    if not launcher_path.is_absolute():
        launcher_path = ROOT / launcher_path
    if not launcher_path.exists():
        slot["status"] = "failed"
        slot["error"] = f"Launcher does not exist: {launcher}"
        log(f"FAIL launch {slot['id']} {slot['job']}: missing launcher")
        return False

    env = build_env(slot)
    launcher_log_dir = MP_DIR / "launcher_logs"
    launcher_log_dir.mkdir(parents=True, exist_ok=True)
    launcher_log_path = launcher_log_dir / f"{slot['id']}-{slot['job']}.log"
    snapshot = job_health_snapshot(slot["job"])

    with launcher_log_path.open("a", encoding="utf-8") as launcher_log:
        launcher_log.write(
            f"[{timestamp()}] START launcher {slot['job']} via {launcher_path}\n"
        )
        launcher_log.flush()
        process = subprocess.Popen(
            [str(launcher_path)],
            cwd=str(ROOT),
            env=env,
            stdout=launcher_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    slot["launched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    slot["launcher_pid"] = process.pid
    slot["launcher_log"] = str(launcher_log_path)
    slot.pop("deferred_at", None)
    slot.pop("defer_reason", None)

    deadline = time.monotonic() + int(config["launch_probe_seconds"])
    while time.monotonic() < deadline:
        if job_started(slot["job"], snapshot):
            break
        if process.poll() is not None:
            break
        time.sleep(0.5)

    if job_started(slot["job"], snapshot) or process.poll() is None:
        if process.poll() is not None:
            process.wait()
            slot["launcher_exit"] = process.returncode
        slot["status"] = "launched"
        log(
            f"LAUNCHED {slot['id']} {slot['job']} "
            f"fb={int(slot['platforms']['facebook_reels'])} "
            f"tt={int(slot['platforms']['tiktok'])} pid={process.pid}"
        )
        return True

    process.wait()
    slot["launcher_exit"] = process.returncode
    if process.returncode == 75:
        slot["status"] = "pending"
        slot["deferred_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        slot["defer_reason"] = "Runner reported another job is active"
        log(f"DEFER {slot['id']} {slot['job']}: runner reported active job")
        return False

    slot["status"] = "failed"
    slot["error"] = (
        f"Launcher exited before job became active. See {launcher_log_path}"
    )
    log(f"FAIL launch {slot['id']} {slot['job']} exit={process.returncode}")
    return False


def run_due_slot(state: dict, config: dict) -> None:
    now = datetime.now()
    grace = timedelta(minutes=config["tick_grace_minutes"])

    for slot in state.get("slots", []):
        if slot.get("status") != "pending":
            continue

        run_at = datetime.strptime(slot["run_at"], "%Y-%m-%d %H:%M:%S")
        if now < run_at:
            continue

        if now > run_at + grace:
            slot["status"] = "skipped_missed"
            slot["skipped_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            log(f"SKIP missed slot {slot['id']} {slot['job']} run_at={slot['run_at']}")
            save_state(state)
            continue

        if active_job_exists():
            log(f"DEFER {slot['id']} {slot['job']}: another MoneyPrinter job is active")
            return

        launch_slot(slot, config)
        save_state(state)
        return

    save_state(state)


def main() -> int:
    config = load_config()
    if not config["enabled"]:
        log("SKIP random_scheduler disabled")
        return 0

    if "--reset-today" in sys.argv and STATE_PATH.exists():
        STATE_PATH.unlink()

    state = load_or_create_state(config)
    if "--generate-only" in sys.argv:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    run_due_slot(state, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
