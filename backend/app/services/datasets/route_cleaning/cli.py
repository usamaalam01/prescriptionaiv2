"""CLI: route cleaning DRY_RUN | STAGE | APPLY_APPROVED.

Examples:
  python -m app.services.datasets.route_cleaning.cli DRY_RUN
  python -m app.services.datasets.route_cleaning.cli STAGE
  python -m app.services.datasets.route_cleaning.cli APPLY_APPROVED --authorize APPLY_APPROVED
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.services.datasets.route_cleaning.pipeline import (
    run_apply_approved,
    run_dry_run,
    run_stage,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PharmaAssist route cleaning pipeline")
    p.add_argument(
        "mode",
        choices=["DRY_RUN", "STAGE", "APPLY_APPROVED"],
        help="Pipeline mode (default safety: DRY_RUN)",
    )
    p.add_argument(
        "--authorize",
        default=None,
        help="Required for APPLY_APPROVED; must equal APPLY_APPROVED",
    )
    p.add_argument(
        "--no-reset",
        action="store_true",
        help="STAGE without clearing prior staging tables",
    )
    args = p.parse_args(argv)

    if args.mode == "DRY_RUN":
        result = run_dry_run()
    elif args.mode == "STAGE":
        result = run_stage(reset=not args.no_reset)
    else:
        result = run_apply_approved(authorize=args.authorize)

    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
