from __future__ import annotations

import argparse

from pathlib import Path

from .autoconfig import configure_query_match
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
    query_parser = sub.add_parser("query-run", help="resolve a FlashScore match from a natural-language query and run the monitor")
    query_parser.add_argument("query", help="for example: Mexico vs England")
    query_parser.add_argument(
        "--config",
        default="",
        help="path to match config JSON, default: match.local.json if present, otherwise match.json",
    )
    prepare_parser = sub.add_parser("query-prepare", help="resolve a FlashScore match from a natural-language query and only update config/curl")
    prepare_parser.add_argument("query", help="for example: Mexico vs England")
    prepare_parser.add_argument(
        "--config",
        default="",
        help="path to match config JSON, default: match.local.json if present, otherwise match.json",
    )

    args = parser.parse_args(argv)
    config_path = args.config or ("match.local.json" if Path("match.local.json").exists() else "match.json")
    if args.command == "run":
        config = load_match_config(config_path)
        return WorldcupMonitor(config).run()
    if args.command == "query-prepare":
        page_info = configure_query_match(config_path, args.query)
        print(f"prepared {page_info.home_team} vs {page_info.away_team}: {page_info.url}")
        return 0
    if args.command == "query-run":
        page_info = configure_query_match(config_path, args.query)
        print(f"prepared {page_info.home_team} vs {page_info.away_team}: {page_info.url}")
        config = load_match_config(config_path)
        return WorldcupMonitor(config).run()
    return 1
