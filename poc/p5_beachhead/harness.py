"""PoC #5 harness — event logging for the 30-minute beachhead validation.

stdlib only (argparse, dataclasses, datetime, json, pathlib, sys) so testers
need no ``pip install``. See ``DESIGN.md`` for methodology, ``SCENARIO.md``
for the protocol, ``RECRUITMENT.md`` for anti-bias rules, ``README.md`` for
the four-step workflow. Output: ``./poc5_results/T<id>_<UTC-ts>.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULTS_DIR = Path("./poc5_results")
ACTIVE_FILE = RESULTS_DIR / ".active.json"


def _utc(fmt: str | None = None) -> str:
    now = datetime.now(UTC)
    return now.strftime(fmt) if fmt else now.isoformat(timespec="seconds")


@dataclass
class Event:
    timestamp: str
    phase: str  # start | log | milestone | finish
    message: str
    tester_id: str


@dataclass
class Session:
    tester_id: str
    started_at: str
    log_path: str

    @classmethod
    def load_active(cls) -> Session:
        if not ACTIVE_FILE.exists():
            sys.exit("no active session; run `harness.py start --tester-id <T>` first")
        return cls(**json.loads(ACTIVE_FILE.read_text(encoding="utf-8")))

    def save_active(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def append(self, phase: str, message: str) -> None:
        log = Path(self.log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        ev = Event(_utc(), phase, message, self.tester_id)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(ev)) + "\n")


def cmd_start(args: argparse.Namespace) -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = (RESULTS_DIR / f"{args.tester_id}_{_utc('%Y-%m-%dT%H-%M-%S')}.jsonl").resolve()
    session = Session(args.tester_id, _utc(), str(log_path))
    session.save_active()
    session.append("start", "session started")
    print(f"started session for {args.tester_id}; log -> {log_path}")
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    msg = getattr(args, "message", None) or args.name
    Session.load_active().append(args.phase, msg)
    print(f"{args.phase}: {msg}")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    session = Session.load_active()
    session.append("finish", "session ended")
    log = Path(session.log_path)
    events: list[dict[str, Any]] = (
        [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if log.exists() else []
    )
    report = {
        "tester_id": session.tester_id,
        "started_at": session.started_at,
        "ended_at": _utc(),
        "rating_would_use_for_real_project_1_to_5": args.rating,
        "worst_friction": args.friction,
        "best_surprise": args.surprise,
        "missing_for_monday_ready": args.missing,
        "events": events,
    }
    report_path = log.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    ACTIVE_FILE.unlink(missing_ok=True)
    print(f"wrote report -> {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PoC #5 beachhead session harness.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start", help="begin a tester session")
    p.add_argument("--tester-id", required=True)
    p.set_defaults(func=cmd_start)
    p = sub.add_parser("log", help="append a free-text event")
    p.add_argument("message")
    p.set_defaults(func=cmd_append, phase="log")
    p = sub.add_parser("milestone", help="mark a named milestone")
    p.add_argument("name")
    p.set_defaults(func=cmd_append, phase="milestone")
    p = sub.add_parser("finish", help="end session + write report")
    p.add_argument("--rating", type=int, required=True, choices=range(1, 6))
    p.add_argument("--friction", required=True)
    p.add_argument("--surprise", required=True)
    p.add_argument("--missing", required=True)
    p.set_defaults(func=cmd_finish)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
