# MachineTrader

MachineTrader is the Python package in this workspace for running systematic trading strategies against Alpaca, replaying strategies against historical minute bars, and sharing the position, order, PnL, timestamp, and logging infrastructure used by those drivers.

The package lives at:

```text
/Users/jerzy/Develop/Python/MachineTrader
```

The project metadata lives one directory above it:

```text
/Users/jerzy/Develop/Python/pyproject.toml
```

## Overview

MachineTrader separates the trading system into four cooperating parts:

1. **Drivers** receive bars, coordinate strategy execution, interact with the broker, and write operational files.
2. **Strategies** calculate indicators and return trade requests or target positions.
3. **Helpers** implement shared argument parsing, market data, broker, position, PnL, timestamp, and file-writing behavior.
4. **Package entry points** make live, momentum, pairs, and backtest drivers runnable from any working directory after an editable install.

A strategy is intended to work with the same context whether its bars come from the live proxy, Alpaca, or a historical replay.

## Installation

From the Python project root:

```bash
cd /Users/jerzy/Develop/Python
python3 -m pip install -e .
```

To validate the package metadata without installing it:

```bash
python3 -m pip install --dry-run --no-deps -e .
```

The package requires Python 3.10 or newer. Its declared dependencies include:

- `alpaca-py`
- `numpy`
- `pandas`
- `python-dotenv`
- `websockets`

After installation, the package can be imported from any working directory:

```python
from MachineTrader.helpers.master_driver_core import MasterDriver
from MachineTrader.master_momentum import MasterMomentumDriver
```

## Package layout

```text
MachineTrader/
├── __init__.py
├── confirm_stream_owner.py
├── master_driver.py
├── master_momentum.py
├── master_backtest.py
├── master_pairs.py
├── strategy_registry.py
├── strat_bollinger_bars.py
├── strat_bollinger_bars_ema.py
├── strat_bollinger_limit.py
├── strat_cross.py
├── strat_ratchet.py
├── strat_trend.py
├── strat_trendfromopen.py
├── strat_trendpreopen.py
├── strat_ratchet_single.py
├── strat_smoke_noop.py
├── strat_tanaka.py
└── helpers/
    ├── alpacasdk.py
    ├── api_parsing.py
    ├── api_responses.py
    ├── args.py
    ├── auth.py
    ├── backtest_sim.py
    ├── broker_orders.py
    ├── calc_ema_class.py
    ├── calc_pnls.py
    ├── common_driver.py
    ├── confirmation_stream.py
    ├── driver_common.py
    ├── driver_entrypoint_helpers.py
    ├── driver_state_helpers.py
    ├── file_handlers.py
    ├── file_writing_helpers.py
    ├── heartbeat.py
    ├── liquidation_limit.py
    ├── live_data.py
    ├── markets.py
    ├── master_driver_core.py
    ├── master_driver_execution.py
    ├── master_driver_orders.py
    ├── metadata.py
    ├── mt_file_handlers.py
    ├── ohlc.py
    ├── order_management.py
    ├── pair_helpers.py
    ├── parse_args.py
    ├── setup_strat.py
    ├── strategy_registry.py
    ├── timestamp_utils.py
    └── utils.py
```

## Driver architecture

All drivers follow the same broad lifecycle:

```text
parse arguments and environment
        |
        v
create strategy callbacks and driver
        |
        v
receive or replay a complete minute bar
        |
        v
process broker confirmations and local queues
        |
        v
run the strategy callback
        |
        v
apply execution policy and submit/cancel orders
        |
        v
write heartbeat, state, blotter, and EOD output
```

The `MasterDriver` class in `helpers/master_driver_core.py` owns the common live orchestration. Specialized drivers inherit from it:

| Driver | Main class | Data and execution mode |
| --- | --- | --- |
| `master_driver.py` | `MasterDriver` | Live proxy bars and Alpaca broker |
| `master_momentum.py` | `MasterMomentumDriver` | Portfolio/momentum bar-driven execution |
| `master_backtest.py` | `MasterMomentumBacktestDriver` | Historical bars and simulated broker |
| `master_pairs.py` | `MasterPairsDriver` | Pair-bar transformation and live execution |

The first driver-migration slice is complete. `CommonDriver` currently owns shared environment hot reload, queue serialization, and basic submitted-order tracking. More broker-event and position-accounting methods can be moved there incrementally after focused validation. Trading-critical execution logic remains in the existing core until each extraction is tested.

## Driver commands

The console entry points are defined in `pyproject.toml`:

```bash
machinetrader-live
machinetrader-momentum
machinetrader-backtest
machinetrader-pairs
```

The equivalent module commands are useful during development:

```bash
cd /Users/jerzy/Develop/Python

python3 -m MachineTrader.master_driver SPY \
    --strategy strat_bollinger_bars:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_strategy

python3 -m MachineTrader.master_momentum \
    --strategy strat_trend:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_momentum_trend

python3 -m MachineTrader.master_pairs \
    --strategy strat_ratchet_single:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_pairs
```

Inspect the exact options before running a driver:

```bash
python3 -m MachineTrader.master_driver --help
python3 -m MachineTrader.master_momentum --help
python3 -m MachineTrader.master_backtest --help
python3 -m MachineTrader.master_pairs --help
```

## Live driver

The live driver consumes bars from the configured data proxy and sends orders through Alpaca. A normal live run requires:

- a running bar proxy;
- a valid environment file with data and trading credentials;
- symbols supplied on the command line or by the environment file;
- a strategy callback that follows the strategy contract;
- an output directory for logs and the local position queue.

Example:

```bash
python3 -m MachineTrader.master_driver SPY \
    --strategy strat_ratchet_single:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_ratchet_spy
```

A strategy request does not submit an Alpaca order directly. The driver applies execution policy, including market-versus-limit choice, order tracking, cancellation, sign-flip handling, and broker-confirmation processing.

Do not use live credentials for a first import or syntax check. Use the no-op strategy and a non-trading environment when testing package wiring.

## Momentum driver

`master_momentum.py` is intended for a portfolio of symbols. The environment file normally supplies the symbol universe and per-symbol quantities. The momentum strategy calculates indicators for the complete bar snapshot, and the driver executes the returned deltas.

```bash
python3 -m MachineTrader.master_momentum \
    --strategy strat_trend:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_momentum_trend
```

The driver compares each new target with the local position maintained from broker confirmations. It must not repeatedly accumulate the same target delta while an earlier order is pending or rejected.

## Pairs driver

`master_pairs.py` converts two symbol bars into one synthetic pair bar before passing it through the normal strategy lifecycle. Pair construction belongs at the data boundary; order tracking, position queues, PnL, and logging are shared with the single-symbol driver.

A pair environment typically defines:

```text
STRATEGY_SYMBOL1=QQQ
STRATEGY_QUANTITY1=1
STRATEGY_SYMBOL2=XLK
STRATEGY_QUANTITY2=1
```

The pair driver calculates the synthetic bar from the configured quantities and uses one consistent pair symbol in state and heartbeat output.

## Backtesting

`master_backtest.py` reuses the momentum driver and replaces the live data source and broker with historical bars and a simulated broker.

```bash
python3 -m MachineTrader.master_backtest \
    --strategy strat_trend:call_back \
    --env-file /Users/jerzy/Develop/trading/config/.env_momentum_trend \
    --date 2026-09-04
```

By default, bars are loaded from:

```text
/Users/jerzy/Develop/data/minutes/live
```

The expected file convention is:

```text
<SYMBOL>_<YYYYMMDD>.csv
```

For each bar, the simulator:

1. fills buy limits when the new low reaches the limit;
2. fills sell limits when the new high reaches the limit;
3. fills pending market orders at the new close;
4. applies fills to the local position queues;
5. passes the new bar and updated positions to the strategy;
6. keeps pending orders when their signed strategy delta is unchanged, or
    cancels and replaces them when that delta changes; and
7. waits for the next bar.

Unfilled orders can remain open for multiple bars. End-of-day liquidation
cancels remaining simulated orders before flattening positions.

Backtest output defaults to a separate directory below the configured log directory, so a replay does not overwrite live logs or the live position queue.

## Strategy contract

Strategies are loaded dynamically from a module and callable specification:

```text
module_name:function_name
```

Examples:

```text
strat_ratchet_single:call_back
strat_trend:call_back
strat_smoke_noop:call_back
```

A callback receives a `StrategyContext`. It can use the current bar, strategy parameters, local positions, and indicator state. A callback returns one of the supported forms:

```python
# Signed deltas: positive means buy, negative means sell.
{"SPY": 2, "NVDA": -1}
```

A list of trade instructions or dictionaries containing a symbol and quantity is also supported. Returning `None` means no trade request for that bar.

Strategies should calculate signals and return intent. They should not call the Alpaca client directly, update broker positions, or submit a second copy of an order.

## Available strategies

| Module | Purpose |
| --- | --- |
| `strat_bollinger_bars.py` | Bollinger-style strategy using bar indicators |
| `strat_bollinger_bars_ema.py` | EMA/Bollinger strategy variant |
| `strat_bollinger_limit.py` | Bollinger strategy with limit-order behavior |
| `strat_cross.py` | Portfolio momentum/crossover strategy |
| `strat_ratchet.py` | Momentum ratchet strategy |
| `strat_trend.py` | Trending momentum strategy |
| `strat_trendpreopen.py` | Pre-open trend strategy variant |
| `strat_trendfromopen.py` | Strategy using the open as a reference |
| `strat_ratchet_single.py` | Ratchet position-sizing strategy |
| `strat_tanaka.py` | Tanaka-style reference-price strategy |
| `strat_smoke_noop.py` | No-op callback for wiring and smoke tests |

Strategy names are runtime inputs. Do not delete a strategy merely because it has no static import: the drivers intentionally load strategies dynamically.

## Shared helpers

| Helper | Responsibility |
| --- | --- |
| `master_driver_core.py` | Main live-driver orchestration |
| `common_driver.py` | Shared migration base for driver state/lifecycle slices |
| `driver_entrypoint_helpers.py` | CLI entrypoint construction and async startup |
| `parse_args.py` and `args.py` | Argument and environment parsing |
| `setup_strat.py` | Strategy setup and parameter preparation |
| `live_data.py` | Proxy/live bar handling |
| `backtest_sim.py` | Simulated clock, broker, API, and bar loading |
| `broker_orders.py` | Broker order operations and status handling |
| `order_management.py` | Shared order execution policy |
| `confirmation_stream.py` | Streaming broker confirmations |
| `calc_pnls.py` | Position and PnL calculations |
| `calc_ema_class.py` | Stateful EMA and z-score calculations |
| `timestamp_utils.py` | Timestamp normalization and New York conversion |
| `markets.py` | Market-calendar behavior |
| `file_handlers.py` | Strategy report and blotter output helpers |
| `heartbeat.py` | Heartbeat formatting and scheduling |
| `api_parsing.py` and `api_responses.py` | Broker response normalization |
| `pair_helpers.py` | Pair configuration and synthetic pair bars |
| `alpacasdk.py` | Alpaca API and trading abstractions |

Use these helpers instead of creating driver-local alternatives. Position queues and PnL must have one source of truth.

## Position queues and PnL

The local position queue is maintained from broker fill confirmations. Broker-reported positions are useful for reconciliation warnings, but should not overwrite the local queue or silently become the PnL source.

The signed-price convention is:

- long entry: negative price, for example `-734.00`;
- short entry: positive price, for example `734.00`.

For a fill in the same direction as the current position, the signed fill price is added to that symbol's queue. For an opposite-direction fill, the queue is matched according to the driver's position policy and realized PnL is updated immediately.

The driver is responsible for:

- filtering confirmations by tracked order ID;
- avoiding duplicate fill accounting;
- using the broker average fill price;
- updating the queue after confirmation;
- calculating realized and unrealized PnL from the local queue; and
- reporting broker/local mismatches without replacing local state.

## Environment configuration

A strategy environment file normally contains credentials, symbols, timing, indicator parameters, and output paths. Common parameters include:

```text
DATA_KEY=...
DATA_SECRET=...
TRADE_KEY=...
TRADE_SECRET=...
DATA_PROXY_URL=ws://localhost:8765
LOG_DIR_NAME=/Users/jerzy/Develop/trading/logs
STRATEGY_NAME=Ratchet
STRATEGY_SYMBOLS=SPY,NVDA
STRATEGY_QUANTITY=1,1
STRATEGY_START_TIME=09:30:00
STRATEGY_END_TIME=16:00:00
STRATEGY_EOD_FLATTEN=true
STRATEGY_ALPHA=0.9
STRATEGY_VOL_FLOOR=0.1
STRATEGY_RISK_PREMIUM=1.0
STRATEGY_LIMIT_SPREAD=1.0
```

Do not commit real credentials. Use a local environment file outside source control. The exact parameter names accepted by a driver are resolved by the shared argument and setup helpers; run the driver with `--help` to inspect them.

## Output files

Live and replay drivers can write several classes of output under the configured log directory:

- state and indicator snapshots;
- heartbeat records;
- trade blotter entries;
- positions and PnL records;
- end-of-day reports; and
- persisted local position queues.

Backtests should write under a separate backtest output directory. Never use a live data or live log directory as a throwaway test target.

## Safe development workflow

Before changing a driver:

1. Run `python3 -m py_compile` on the affected package modules.
2. Import the driver and strategy without starting a broker stream.
3. Run the no-op strategy with a non-trading environment.
4. Use the backtest simulator for execution-policy changes.
5. Inspect the blotter, position queue, and PnL output together.
6. Only then run a paper-trading smoke session.

Useful checks:

```bash
cd /Users/jerzy/Develop/Python
python3 -m py_compile MachineTrader/*.py MachineTrader/helpers/*.py
python3 -m pip install --dry-run --no-deps -e .
python3 -m MachineTrader.master_driver --help
python3 -m MachineTrader.master_momentum --help
python3 -m MachineTrader.master_backtest --help
python3 -m MachineTrader.master_pairs --help
```

## Migration status

The package conversion is being performed incrementally to protect live execution behavior.

Completed first-stage work:

- added `pyproject.toml` at the Python project root;
- added package discovery for `MachineTrader*`;
- added editable-install driver entry points;
- moved selected shared driver behavior into `helpers/common_driver.py`;
- kept existing driver module names and CLI commands compatible; and
- removed the broken legacy `AlpacaSDK` alias from package initialization.

The next safe migration slices are broker confirmation ingestion, queue loading and persistence, and then the remaining shared order-management state. Each slice should be compiled and import-tested before the next one is moved.
