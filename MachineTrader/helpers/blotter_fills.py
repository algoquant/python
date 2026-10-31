from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from MachineTrader.helpers.file_handlers import (
    discover_dated_csv_files,
    extract_signed_fills_from_blotters,
)


DEFAULT_LOG_DIR = Path("/Users/jerzy/Develop/trading/logs")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI that extracts and writes a strategy's consolidated fills."""
    parser = argparse.ArgumentParser(
        description="Extract incremental fills from dated strategy blotter CSV files.",
        epilog="Input filenames must match <strategy>_blotter_YYYYMMDD.csv. "
        "The default output is <log_dir>/<STRATEGY_NAME>_fills.csv.",
    )
    parser.add_argument("STRATEGY_NAME", nargs="?", help="Blotter filename prefix (default: Ladder).")
    parser.add_argument("--strategy", help="Blotter filename prefix (legacy named form of STRATEGY_NAME).")
    parser.add_argument("--log_dir", type=Path, default=DEFAULT_LOG_DIR, help="Directory containing daily blotters.")
    parser.add_argument("--output", type=Path, help="Output CSV path (default: <log_dir>/<STRATEGY_NAME>_fills.csv).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file.")
    args = parser.parse_args(argv)

    if args.STRATEGY_NAME and args.strategy:
        parser.error("provide STRATEGY_NAME or --strategy, not both")

    strategy = (args.STRATEGY_NAME or args.strategy or "Ladder").strip()
    if not strategy:
        parser.error("STRATEGY_NAME cannot be empty")

    output_path = (args.output or args.log_dir / f"{strategy}_fills.csv").expanduser()
    if output_path.exists() and not args.overwrite:
        print(
            f"Refusing to overwrite existing output: {output_path} (pass --overwrite to replace it)",
            file=sys.stderr,
        )
        return 2

    dated_paths = discover_dated_csv_files(args.log_dir, [f"{strategy}_blotter_*.csv"])
    if not dated_paths:
        print(f"No dated {strategy} blotters found in {args.log_dir}", file=sys.stderr)
        return 1

    fills = extract_signed_fills_from_blotters([path for _, path in dated_paths])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fills.to_csv(output_path, index=False)
    print(f"Wrote {len(fills)} fills from {len(dated_paths)} blotters to {output_path}")
    return 0