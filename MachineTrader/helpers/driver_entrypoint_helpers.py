from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from MachineTrader.helpers.parse_args import create_common_driver_arg_parser
from MachineTrader.helpers.setup_strat import build_strategy_functions, build_strategy_params


def run_async_entrypoint(
    main_coro_factory: Callable[[], Awaitable[None]],
    *,
    print_fn=print,
    interrupted_message: str = "Interrupted by user",
    runtime_error_help: str = "",
) -> int:
    """Run async driver entrypoint with consistent Ctrl-C and runtime error handling."""
    try:
        asyncio.run(main_coro_factory())
        return 0
    except KeyboardInterrupt:
        print_fn("🛑 ", interrupted_message)
        return 130
    except RuntimeError as exc:
        print_fn("⚠️ ", str(exc))
        if str(runtime_error_help or "").strip():
            print_fn("ℹ️ ", runtime_error_help)
        return 1

__all__ = [
    "build_strategy_functions",
    "build_strategy_params",
    "create_common_driver_arg_parser",
    "run_async_entrypoint",
]
