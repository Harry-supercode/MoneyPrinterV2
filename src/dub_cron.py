import sys

from classes.DubPipeline import DubPipeline
from llm_provider import select_model
from status import error, warning


def main() -> None:
    account_id = str(sys.argv[1]) if len(sys.argv) > 1 else ""
    model = str(sys.argv[2]) if len(sys.argv) > 2 else ""

    if model:
        select_model(model)

    try:
        DubPipeline(account_id=account_id).run()
    except KeyboardInterrupt:
        warning("Dub pipeline cancelled by user.")
    except Exception as exc:
        error(f"Dub pipeline failed: {exc}")
        raise


if __name__ == "__main__":
    main()
