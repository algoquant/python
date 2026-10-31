from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from MachineTrader.helpers.file_handlers import (
    discover_dated_csv_files,
    extract_signed_orders_from_blotters,
)


DEFAULT_LOG_DIR = Path("/Users/jerzy/Develop/trading/logs")


def main(argv: Sequence[str] | None = None) -> int:
    """Extract daily submitted orders for one strategy into a CSV file."""
    parser = argparse.ArgumentParser(
        description="Extract submitted orders from dated strategy blotter CSV files.",
        epilog="Input filenames must match <STRATEGY_NAME>_blotter_YYYYMMDD.csv. "
        "Output columns are timestamp, symbol, signed qty, and oppositely signed limit_price. "
        "The default output is <log_dir>/<STRATEGY_NAME>_orders.csv.",
    )
    parser.add_argument("STRATEGY_NAME", nargs="?", help="Blotter filename prefix, such as Ladder.")
    parser.add_argument("--strategy", help="Blotter filename prefix (named form of STRATEGY_NAME).")
    parser.add_argument("--log_dir", type=Path, default=DEFAULT_LOG_DIR, help="Directory containing daily blotters.")
    parser.add_argument("--output", type=Path, help="Output CSV path (default: <log_dir>/<STRATEGY_NAME>_orders.csv).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file.")
    args = parser.parse_args(argv)

    if args.STRATEGY_NAME and args.strategy:
        parser.error("provide STRATEGY_NAME or --strategy, not both")

    strategy = (args.STRATEGY_NAME or args.strategy or "").strip()
    if not strategy:
        parser.error("STRATEGY_NAME or --strategy is required")

    output_path = (args.output or args.log_dir / f"{strategy}_orders.csv").expanduser()
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

    orders = extract_signed_orders_from_blotters([path for _, path in dated_paths])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    orders.to_csv(output_path, index=False)
    print(f"Wrote {len(orders)} orders from {len(dated_paths)} blotters to {output_path}")
    return 0