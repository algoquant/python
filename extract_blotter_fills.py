"""Extract signed execution fills from dated strategy blotter CSV files.

The command searches a log directory for files named
``<strategy>_blotter_YYYYMMDD.csv`` and processes them in date order. Only
files whose names end in an eight-digit date are considered. For example, the
default strategy, ``Ladder``, matches ``Ladder_blotter_20261015.csv``.

Each accepted fill is written as one row with these columns:

* ``timestamp``: broker event time, normalized to New York time.
* ``symbol``: upper-case ticker symbol.
* ``num_shares``: positive quantity for both buys and sells.
* ``fill_price``: negative for buys and positive for sells, following the
    signed-price convention used by the position queue.

The underlying extractor ignores unreadable or malformed blotter files,
deduplicates repeated broker execution IDs, and uses cumulative filled
quantities to recover an incremental quantity when an event does not provide
one. Executions from the same order, symbol, and side whose timestamps span
less than one minute are consolidated into one row, using a share-weighted
price. Rows without a usable side, positive quantity, positive price, or
timestamp are omitted. This command does not modify its input blotters.

By default, output is written to ``<log_dir>/<STRATEGY_NAME>_fills.csv``;
``STRATEGY_NAME`` is the positional strategy name, or ``Ladder`` when omitted.
Existing output is protected: pass ``--overwrite`` to replace it. The output
directory is created when needed.

Examples::

        python extract_blotter_fills.py
        python extract_blotter_fills.py Momentum --log_dir ~/trading/logs
        python extract_blotter_fills.py --strategy Ladder --output /tmp/ladder.csv
        python extract_blotter_fills.py --strategy Ladder --overwrite

Exit status is 0 on success, 1 when no dated blotters are found, and 2 when
the output already exists and overwrite was not authorized (or arguments are
invalid).
"""

from MachineTrader.helpers.blotter_fills import main


if __name__ == "__main__":
    raise SystemExit(main())
