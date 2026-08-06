from dataclasses import dataclass


@dataclass(frozen=True)
class DubRunContext:
    run_dir: str
    run_id: str
    config: dict

