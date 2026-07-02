from __future__ import annotations

import argparse

from pathlib import Path

from .config import load_match_config
from .monitor import WorldcupMonitor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldcup-monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run a match goal monitor")
    run_parser.add_argument(
        "--config",
        default="",
        help="path to match config JSON, default: match.local.json if present, otherwise match.json",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        config_path = args.config or ("match.local.json" if Path("match.local.json").exists() else "match.json")
        config = load_match_config(config_path)
        return WorldcupMonitor(config).run()
    return 1
