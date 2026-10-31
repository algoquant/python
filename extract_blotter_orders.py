"""Extract submitted orders from daily strategy blotters.

The shared extractor reads dated ``<STRATEGY_NAME>_blotter_YYYYMMDD.csv``
files and writes one row for each submitted order, deduplicated by order ID.
Output columns are ``timestamp``, ``symbol``, ``qty``, and ``limit_price``.
Quantity keeps its blotter sign; price has the opposite sign (negative for
buys, positive for sells). Limit orders use their submitted limit price.
Market and limit orders both use the blotter's ``limit_price`` field; fill
prices do not replace it. If that field is blank, the exported price is blank.

By default, the output is ``<log_dir>/<STRATEGY_NAME>_orders.csv``. Existing
output is not overwritten unless ``--overwrite`` is supplied.

Examples::

    python extract_blotter_orders.py Ladder
    python extract_blotter_orders.py Momentum --log_dir ~/trading/logs
    python extract_blotter_orders.py Ladder --output /tmp/ladder_orders.csv
    python extract_blotter_orders.py Ladder --overwrite

Run ``python extract_blotter_orders.py --help`` for all options.
"""

from MachineTrader.helpers.blotter_orders import main


if __name__ == "__main__":
    raise SystemExit(main())