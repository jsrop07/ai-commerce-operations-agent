"""Read-only sync command-line interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from backend.app.sync.run_lock import SyncRunLock

_RUN_LOCK = SyncRunLock()


@dataclass(frozen=True)
class SyncCliOptions:
    provider: str
    resource: str
    since: datetime | None
    max_pages: int
    dry_run: bool


@dataclass(frozen=True)
class SyncExecutionResult:
    status: str
    plan: dict[str, object]


def _parse_since(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("since must be an ISO-8601 datetime") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("since must include timezone")

    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded provider/resource synchronization.")

    parser.add_argument(
        "--provider",
        required=True,
        help="Provider identifier.",
    )
    parser.add_argument(
        "--resource",
        required=True,
        help="Provider resource to synchronize.",
    )
    parser.add_argument(
        "--since",
        type=_parse_since,
        default=None,
        help="Optional ISO-8601 lower bound with timezone.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Maximum number of pages to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the sync plan without committing checkpoints/effects.",
    )

    return parser


def parse_args(
    argv: Sequence[str] | None = None,
) -> SyncCliOptions:
    args = build_parser().parse_args(argv)

    provider = args.provider.strip()
    resource = args.resource.strip()

    if not provider:
        raise ValueError("provider is required")
    if not resource:
        raise ValueError("resource is required")
    if args.max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    return SyncCliOptions(
        provider=provider,
        resource=resource,
        since=args.since,
        max_pages=args.max_pages,
        dry_run=args.dry_run,
    )


def build_sync_plan(
    options: SyncCliOptions,
) -> dict[str, object]:
    return {
        "provider": options.provider,
        "resource": options.resource,
        "since": (options.since.isoformat() if options.since is not None else None),
        "max_pages": options.max_pages,
        "dry_run": options.dry_run,
        "execution_status": "PLAN_ONLY",
        "external_write_count": 0,
    }


def execute_sync_plan(
    *,
    tenant_id: str,
    options: SyncCliOptions,
    run_lock: SyncRunLock | None = None,
) -> SyncExecutionResult:
    lock = run_lock or _RUN_LOCK
    plan = build_sync_plan(options)

    acquired = lock.acquire(
        tenant_id=tenant_id,
        provider=options.provider,
        resource=options.resource,
    )

    if not acquired:
        return SyncExecutionResult(
            status="LOCKED",
            plan={
                **plan,
                "execution_status": "LOCKED",
            },
        )

    try:
        # Day 7에서는 아직 실제 scheduler/live provider 실행을
        # 여기서 자동 시작하지 않는다.
        return SyncExecutionResult(
            status="PLAN_ONLY",
            plan=plan,
        )
    finally:
        lock.release(
            tenant_id=tenant_id,
            provider=options.provider,
            resource=options.resource,
        )


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_args(argv)
    plan = build_sync_plan(options)

    print(
        json.dumps(
            plan,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
