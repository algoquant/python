"""Parse and display MachineTrader strategy arguments.

This script is a small executable wrapper around the argument-handling API in
the :mod:`MachineTrader` package. It intentionally does not define a local
``parse_arguments()`` implementation, so parser options, defaults, and
validation remain centralized in the package.

Execution flow:
    1. Parse the command line with ``MachineTrader.parse_arguments``.
    2. Prompt for required values when any are missing, or when
       ``--interactive`` is present.
    3. Ask the user to confirm values collected interactively.
    4. Print the resulting ``argparse.Namespace`` as key/value pairs.

Supplying no arguments is treated differently from interactive mode: the
script prints guidance and exits with status 1. A rejected interactive
confirmation is a deliberate cancellation and exits with status 0. Fully
specified command lines do not require confirmation.

Examples:
    Run with selected options (other missing values are prompted for)::

        python3 parse_arguments_mt.py trade_zscore SPY \
            --shares_per_trade 1 --order_type limit --alpha 0.3

    Provide a different subset of strategy options::

        python3 parse_arguments_mt.py trade_zscore AAPL \
            --shares_per_trade 10 --thresholdz 2.0 --delay 5.0

    Prompt for values interactively::

        python3 parse_arguments_mt.py --interactive

Use ``python3 parse_arguments_mt.py --help`` for the authoritative option list
provided by the installed MachineTrader package.
"""

import sys
from MachineTrader import parse_arguments, prompt_for_missing_args, confirm_parameters


if __name__ == "__main__":
    args = parse_arguments()

    # A partial command line falls back to prompts rather than failing. Keep
    # this list aligned with the values requested by prompt_for_missing_args().
    missing_args = (
        not args.strategy_function
        or not args.symbol
        or args.shares_per_trade is None
        or args.order_type is None
        or args.alpha is None
        or args.vol_floor is None
        or args.thresholdz is None
        or args.take_profit is None
        or args.delay is None
        or not args.indicator_name
        or args.interactive
    )

    # Keep the explicit no-args behavior used by the original script.
    if len(sys.argv) == 1:
        print("No arguments provided. Re-run with --interactive or provide command line parameters.")
        sys.exit(1)

    if missing_args:
        if len(sys.argv) > 1:
            print("Some arguments are missing or --interactive mode requested.")
        args = prompt_for_missing_args(args)

        if not confirm_parameters(args):
            print("Operation cancelled by user.")
            sys.exit(0)

    # vars() preserves every parser field, including package options added in
    # future releases, without duplicating their names in this wrapper.
    print("\nArguments dictionary:")
    for key, value in vars(args).items():
        print(f"  {key}: {value}")
