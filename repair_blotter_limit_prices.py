"""Fill blank blotter limit prices from the nearest symbol minute-bar close.

Dry-run by default. Pass ``--apply`` to update the dated strategy blotters;
original files are copied to a timestamped sibling backup directory first.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import io
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from MachineTrader.helpers.timestamp_utils import coerce_datetime_ny


DEFAULT_LOG_DIR = Path("/Users/jerzy/Develop/trading/logs")
DEFAULT_PRICE_DIR = Path("/Users/jerzy/Develop/data/minutes/live")
BLOTTER_PATTERN = re.compile(r"_blotter_\d{8}\.csv$")
PRICE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9.-]*)_(\d{8})\.csv$", re.IGNORECASE)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--price-dir", type=Path, default=DEFAULT_PRICE_DIR)
    parser.add_argument("--apply", action="store_true", help="Write repairs after backing up originals")
    parser.add_argument("--backup-dir", type=Path, help="Backup directory (defaults beside the log directory)")
    parser.add_argument("--verbose", action="store_true", help="Print each repaired row and its selected price bar")
    return parser.parse_args()


def _index_price_files(price_dir: Path) -> dict[str, list[Path]]:
    files_by_symbol: dict[str, list[Path]] = {}
    for path in price_dir.glob("*.csv"):
        match = PRICE_PATTERN.match(path.name)
        if match:
            files_by_symbol.setdefault(match.group(1).upper(), []).append(path)
    for paths in files_by_symbol.values():
        paths.sort()
    return files_by_symbol


def _load_symbol_prices(
    price_files_by_symbol: dict[str, list[Path]],
    symbol: str,
) -> list[tuple[datetime, float, Path]]:
    symbol_prices: list[tuple[datetime, float, Path]] = []
    for path in price_files_by_symbol.get(symbol.upper(), []):
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if not {"timestamp", "close"}.issubset(reader.fieldnames or []):
                    continue
                for row in reader:
                    timestamp = coerce_datetime_ny(row.get("timestamp"), fallback_to_now=False)
                    try:
                        close = float(row.get("close", ""))
                    except (TypeError, ValueError):
                        continue
                    if timestamp is not None and close > 0:
                        symbol_prices.append((timestamp, close, path))
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
    return symbol_prices


def _nearest_close(
    price_rows: list[tuple[datetime, float, Path]],
    timestamp: datetime,
) -> tuple[float, datetime, Path] | None:
    if not price_rows:
        return None
    nearest_timestamp, close, path = min(
        price_rows,
        key=lambda row: (abs((row[0] - timestamp).total_seconds()), row[0]),
    )
    return close, nearest_timestamp, path


def _prepare_blotter(
    path: Path,
    price_dir: Path,
    price_cache: dict[str, list[tuple[datetime, float, Path]]],
    price_files_by_symbol: dict[str, list[Path]],
    *,
    verbose: bool = False,
):
    raw_bytes = path.read_bytes()
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    text = raw_bytes.decode("utf-8-sig")
    line_ending = "\r\n" if "\r\n" in text else "\n"
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return raw_bytes, 0, []

    header = rows[0]
    timestamp_fields = ("timestamp", "timestamp_ny", "broker_timestamp")
    if "symbol" not in header or not (set(timestamp_fields) & set(header)):
        return raw_bytes, 0, [(0, "missing symbol or timestamp column")]

    added_limit_column = "limit_price" not in header
    original_header_length = len(header)
    if "limit_price" in header:
        limit_index = header.index("limit_price")
    else:
        limit_index = header.index("order_type") + 1 if "order_type" in header else len(header)
        header.insert(limit_index, "limit_price")

    timestamp_indices = [header.index(name) for name in timestamp_fields if name in header]
    symbol_index = header.index("symbol")
    repairs = 0
    unresolved: list[tuple[int, str]] = []

    for row_number, row in enumerate(rows[1:], start=2):
        if added_limit_column:
            if len(row) < original_header_length:
                row.extend([""] * (original_header_length - len(row)))
            row.insert(limit_index, "")
        elif len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))

        if str(row[limit_index] or "").strip():
            continue

        symbol = str(row[symbol_index] or "").strip().upper()
        raw_timestamp = next((row[index] for index in timestamp_indices if index < len(row) and str(row[index]).strip()), "")
        timestamp = coerce_datetime_ny(raw_timestamp, fallback_to_now=False)
        if not symbol or timestamp is None:
            unresolved.append((row_number, "missing symbol or parseable timestamp"))
            continue

        if symbol not in price_cache:
            price_cache[symbol] = _load_symbol_prices(price_files_by_symbol, symbol)
        nearest = _nearest_close(price_cache[symbol], timestamp)
        if nearest is None:
            unresolved.append((row_number, f"no valid price bars for {symbol}"))
            continue

        close, price_timestamp, price_path = nearest
        if limit_index >= len(row):
            row.extend([""] * (limit_index - len(row) + 1))
        row[limit_index] = f"{close:.10g}"
        repairs += 1
        distance_seconds = abs((price_timestamp - timestamp).total_seconds())
        if verbose:
            print(
                f"  {path.name}:{row_number} {symbol} {raw_timestamp} -> {close:.10g} "
                f"from {price_path.name} at {price_timestamp.isoformat()} "
                f"(distance {distance_seconds:.1f}s)"
            )

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=line_ending)
    writer.writerows(rows)
    encoded = output.getvalue().encode("utf-8")
    if has_bom:
        encoded = b"\xef\xbb\xbf" + encoded
    return encoded, repairs, unresolved


def repair_blotters(
    log_dir: Path,
    price_dir: Path,
    *,
    apply: bool = False,
    backup_dir: Path | None = None,
    verbose: bool = False,
) -> tuple[int, int, int]:
    paths = sorted(path for path in log_dir.glob("*_blotter_*.csv") if BLOTTER_PATTERN.search(path.name))
    price_cache: dict[str, list[tuple[datetime, float, Path]]] = {}
    prepared = []
    file_errors = 0
    total_repairs = 0
    total_unresolved = 0
    unresolved_reasons: Counter[str] = Counter()
    unresolved_samples: list[tuple[str, int, str]] = []
    price_files_by_symbol = _index_price_files(price_dir)

    for path in paths:
        try:
            encoded, repairs, unresolved = _prepare_blotter(
                path,
                price_dir,
                price_cache,
                price_files_by_symbol,
                verbose=verbose,
            )
        except (OSError, csv.Error, UnicodeDecodeError) as error:
            print(f"ERROR {path.name}: {error}")
            file_errors += 1
            continue
        total_repairs += repairs
        total_unresolved += len(unresolved)
        for row_number, reason in unresolved:
            unresolved_reasons[reason] += 1
            if len(unresolved_samples) < 20:
                unresolved_samples.append((path.name, row_number, reason))
        for row_number, reason in unresolved:
            if verbose:
                print(f"UNRESOLVED {path.name}:{row_number}: {reason}")
        if repairs:
            prepared.append((path, encoded))
            print(f"{path.name}: {repairs} repair(s), {len(unresolved)} unresolved")

    if apply and file_errors:
        print("Not applying changes: file-read errors occurred. Resolve them before rerunning with --apply.")
        return total_repairs, total_unresolved, file_errors

    if apply and prepared:
        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        actual_backup_dir = backup_dir or log_dir.parent / f"{log_dir.name}_blotter_backup_{run_stamp}"
        actual_backup_dir.mkdir(parents=True, exist_ok=False)
        for path, encoded in prepared:
            shutil.copy2(path, actual_backup_dir / path.name)
            mode = path.stat().st_mode
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
                temporary_path = Path(stream.name)
                stream.write(encoded)
            temporary_path.chmod(mode)
            temporary_path.replace(path)
        print(f"Updated {len(prepared)} blotter file(s); originals backed up in {actual_backup_dir}")
    elif not apply:
        print("Dry run only. Pass --apply to write changes after a backup is created.")

    print(
        f"Summary: {len(paths)} files scanned, {total_repairs} missing limit_price value(s) "
        f"repairable, {total_unresolved} unresolved, {file_errors} file error(s)."
    )
    for reason, count in unresolved_reasons.most_common():
        print(f"Unresolved category: {reason}: {count}")
    for filename, row_number, reason in unresolved_samples:
        print(f"Unresolved sample: {filename}:{row_number}: {reason}")
    return total_repairs, total_unresolved, file_errors


def main() -> int:
    args = _parse_args()
    repairs, unresolved, errors = repair_blotters(
        args.log_dir.expanduser(),
        args.price_dir.expanduser(),
        apply=args.apply,
        backup_dir=args.backup_dir.expanduser() if args.backup_dir else None,
        verbose=args.verbose,
    )
    return 1 if unresolved or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())