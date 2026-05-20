# ---------------------------------------------------------
# Convert OHLCV column names to TICKER.Field format in all the 
# Parquet files in the /Users/jerzy/Develop/data/daily directory.
# ---------------------------------------------------------

from pathlib import Path
import re

import pandas as pd


DATA_DIR = Path("/Users/jerzy/Develop/data/daily")


def _derive_ticker(df: pd.DataFrame, parquet_path: Path) -> str | None:
	"""Derive ticker from a single-value ticker column or from file name."""
	if "ticker" in df.columns:
		non_null = df["ticker"].dropna().astype(str).str.strip().str.upper()
		if not non_null.empty:
			ticker = non_null.iloc[0]
			if re.fullmatch(r"[A-Z][A-Z0-9.\-]*", ticker):
				return ticker

	stem = parquet_path.stem.upper()
	stem = stem.replace("_DAILY", "")
	if re.fullmatch(r"[A-Z][A-Z0-9.\-]*", stem):
		return stem
	return None


def _get_col_case_insensitive(df: pd.DataFrame, col_name: str) -> str | None:
	target = col_name.lower()
	for col in df.columns:
		if str(col).lower() == target:
			return str(col)
	return None


def _convert_one_file(parquet_path: Path) -> tuple[bool, str]:
	df = pd.read_parquet(parquet_path)
	if df.empty:
		return False, "empty"

	ticker = _derive_ticker(df, parquet_path)
	if not ticker:
		return False, "missing_ticker"

	rename_plan = {
		"open": f"{ticker}.Open",
		"high": f"{ticker}.High",
		"low": f"{ticker}.Low",
		"close": f"{ticker}.Close",
		"volume": f"{ticker}.Volume",
		"dollar_volume": f"{ticker}.VolumeD",
		"volumed": f"{ticker}.VolumeD",
	}

	rename_map = {}
	for source_name, target_name in rename_plan.items():
		source_col = _get_col_case_insensitive(df, source_name)
		if source_col and target_name not in df.columns:
			rename_map[source_col] = target_name

	already_prefixed = any(str(col).startswith(f"{ticker}.") for col in df.columns)
	changed = False

	if rename_map:
		df = df.rename(columns=rename_map)
		changed = True

	if "ticker" in df.columns:
		df = df.drop(columns=["ticker"])
		changed = True

	# Reorder key columns when present: date, prefixed OHLCV, then everything else.
	ordered = []
	date_col = _get_col_case_insensitive(df, "date")
	if date_col:
		ordered.append(date_col)

	for suffix in ("Open", "High", "Low", "Close", "Volume", "VolumeD"):
		col = f"{ticker}.{suffix}"
		if col in df.columns:
			ordered.append(col)

	remaining = [c for c in df.columns if c not in ordered]
	df = df[ordered + remaining]

	if changed or already_prefixed:
		df.to_parquet(parquet_path, index=False)
		return True, "converted"

	return False, "no_ohlcv_columns"


def main() -> None:
	if not DATA_DIR.exists():
		raise FileNotFoundError(f"Directory not found: {DATA_DIR}")

	parquet_files = sorted(DATA_DIR.glob("*.parquet"))
	if not parquet_files:
		print(f"No parquet files found in {DATA_DIR}")
		return

	converted = 0
	skipped = 0
	skipped_by_reason: dict[str, int] = {}

	for i, parquet_path in enumerate(parquet_files, start=1):
		try:
			did_convert, reason = _convert_one_file(parquet_path)
		except Exception as exc:
			did_convert = False
			reason = f"error:{type(exc).__name__}"

		if did_convert:
			converted += 1
		else:
			skipped += 1
			skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1

		if i % 200 == 0 or i == len(parquet_files):
			print(f"Processed {i}/{len(parquet_files)} files...")

	print("Conversion complete.")
	print(f"Converted: {converted}")
	print(f"Skipped: {skipped}")
	if skipped_by_reason:
		print("Skip reasons:")
		for reason, count in sorted(skipped_by_reason.items()):
			print(f"  {reason}: {count}")


if __name__ == "__main__":
	main()

