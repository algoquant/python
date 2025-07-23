# --------- Get the trading symbols from the command line arguments --------

import sys

# Get multiple symbols from command line arguments
if len(sys.argv) > 1:
    # Take all arguments after the script name as symbols
    symbols = [arg.strip().upper() for arg in sys.argv[1:]]
else:
    # If no arguments, prompt for symbols
    symbol_input = input("Enter symbols (comma-separated, e.g., SPY,AAPL,GOOGL): ").strip().upper()
    symbols = [s.strip() for s in symbol_input.split(',') if s.strip()]

print(f"These are the input symbols: {', '.join(symbols)}\n")

