from __future__ import annotations

import argparse

from .config import load_match_config
from .monitor import WorldcupMonitor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldcup-monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run a match goal monitor")
    run_parser.add_argument("--config", required=True, help="path to match config JSON")

    args = parser.parse_args(argv)
    if args.command == "run":
        config = load_match_config(args.config)
        return WorldcupMonitor(config).run()
    return 1
