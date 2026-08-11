import argparse
import json
import os
import sys

from classes.SocialPostPipeline import SocialPostPipeline
from llm_provider import select_model
from status import error, success


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run browser-based social text/image post job.")
    parser.add_argument(
        "--platform",
        choices=["all", "facebook", "youtube"],
        default=os.environ.get("MPV2_SOCIAL_POST_PLATFORM", "all"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MPV2_OLLAMA_MODEL", "llama3.2:3b"),
        help="Ollama model name for post generation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("MPV2_SOCIAL_POST_DRY_RUN", "").lower()
        in {"1", "true", "yes", "on"},
        help="Generate and save a draft without publishing.",
    )
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        default=os.environ.get("MPV2_SOCIAL_POST_ALLOW_UNVERIFIED", "").lower()
        in {"1", "true", "yes", "on"},
        help="Allow publishing before social_posts.automation_verified=true.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.model:
        select_model(args.model)

    try:
        result = SocialPostPipeline().run(
            platform=args.platform,
            dry_run=args.dry_run,
            allow_unverified=args.allow_unverified,
        )
    except Exception as exc:
        error(f"Social post job failed: {exc}")
        return 78 if "automation_verified" in str(exc) else 1

    success(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
