"""
This is a strategy script for trading stocks using the Alpaca API.
It first creates a strategy object, which is an instance of the Strategies class, and then it subscribes to the bar data stream via the proxy server.
It passes the bar data to the strategy object via the Bar.stream_bars method.

Strategy trades a single stock using the streaming real-time stock price bars from the proxy server - not directly the Alpaca API.
The strategy is based on the Z-score, equal to the difference between the stock's price minus its Moving Average Price (EMA), divided by the volatility.

    Z-score = (price - EMA) / volatility

The strategy uses streaming bar prices and streaming confirms via the proxy server.

The strategy either takes profit if the unrealized P&L is above a certain threshold, or it executes the contrarian rule based on the Z-score.

The strategy uses the contrarian rule based on the Bollinger Bands concept, where the Z-score indicates if the stock is cheap or rich (expensive).

To run the strategy, first change the path to the .env file.
Then run the strategy by executing this script with the appropriate parameters in the terminal:
    python3 strat_bollinger_bars_vwap.py symbol num_shares type alpha vol_floor risk_premium take_profit_factor delay
For example:
    python3 strat_bollinger_bars_proxy.py SPY 1 limit 0.3 0.1 2.0 20.0 5.0

# Simple usage with defaults
python3 strat_bollinger_bars_proxy.py SPY

# With specific parameters
python3 strat_bollinger_bars_proxy.py SPY --shares 10 --type market --alpha 0.3

# Full parameter specification
python3 strat_bollinger_bars_proxy.py AAPL --shares 5 --type limit --alpha 0.2 --vol-floor 0.05 --risk-premium 1.5 --take-profit 15.0 --delay 2.0 --strategy=trade_zscore

The num_shares parameter specifies the number of shares for each trade.

The type parameter specifies the order type, either "market" or "limit".

The alpha parameter is the EMA decay parameter (0 < alpha <= 1).
It's used to calculate the Exponential Moving Average (EMA) of the stock price.
Larger alpha values apply more weight to past prices, with more smoothing, and a slower response to new prices.
Smaller alpha values provide less smoothing and a faster response to new prices.

The vol_floor is the minimum value of the dollar volatility used in the Z-score calculations.
This prevents division by very small numbers when the price volatility is low.
Typical values range from 0.01 to 0.2 depending on the asset and the time horizon.

The risk_premium parameter serves two purposes:
1. It adjusts the limit price for limit orders.
2. It serves as the threshold for the Z-score.

The risk_premium parameter is used to determine the limit price, compared to the ask or bid price.
The limit price adjustment pa is equal to the risk_premium parameter times the volatility.
For example, if the risk_premium is 2.0 and the volatility is $0.1, then the price adjustment pa is $0.2.
If the ask price is $100, then the limit buy price is set to $99.8.
If the bid price is $99, then the limit sell price is set to $99.2.
The subsequent limit order prices are spread apart by the price adjustment pa, to avoid submitting multiple limit orders at the same price.
If another limit order is submitted, then its price is set based on the previous limit order price and the risk_premium parameter.
For example, the next limit buy price after $99.8 would be set to $99.6.
This is to avoid submitting multiple limit orders at the same price.

The risk_premium serves as the threshold level for the Z-score.
If the Z-score is between -risk_premium and risk_premium, then the strategy does not trade.
If the Z-score is below -risk_premium, then it buys the stock.
If the Z-score is above +risk_premium, then it sells the stock.
It submits either limit or market orders when the Z-score is above +risk_premium or below -risk_premium.

The take_profit_factor is used to determine the take profit level for the strategy.
It is a multiplier applied to the average cost basis of the position.
For example, if the take_profit_factor is 2.0 and the average cost basis is $100, then the take profit level is set to $102.

The delay parameter specifies the number of seconds to wait before submitting trade orders.
This delay allows for better timing control and can help avoid rapid-fire trading.
For example, if the delay is 5.0, then the strategy will wait 5 seconds before submitting each trade order.
A delay of 0.0 means no delay (immediate order submission).

NOTE:
This script is only for illustration purposes, and not a real trading strategy.
This is only an illustration how to use the streaming real-time data from the proxy server.
"""


import argparse
import asyncio
from zoneinfo import ZoneInfo
from MachineTrader import Bar, CreateStrategy


# --------- Get the trading parameters from the command line arguments --------

# Define a function to parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Bollinger Bands trading strategy using Alpaca API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 strat_bollinger_bars_proxy.py SPY --shares 1 --type limit --alpha 0.3
  python3 strat_bollinger_bars_proxy.py AAPL --shares 10 --risk-premium 2.0 --delay 5.0
        """
    )
    
    # Required arguments
    parser.add_argument('symbol', help='Stock symbol to trade (e.g., SPY, AAPL)')
    
    # Optional arguments with defaults
    parser.add_argument('--shares', type=float, default=1.0, 
                       help='Number of shares per trade (default: 1.0)')
    parser.add_argument('--type', choices=['market', 'limit'], default='limit',
                       help='Order type: market or limit (default: limit)')
    parser.add_argument('--alpha', type=float, default=0.1,
                       help='EMA decay factor 0 < alpha <= 1 (default: 0.1) - larger values produce smoother EMA')
    parser.add_argument('--vol_floor', type=float, default=0.1,
                       help='Minimum volatility floor (default: 0.1)')
    parser.add_argument('--risk_premium', type=float, default=2.0,
                       help='The Z-score threshold (default: 2.0) - trade if the Z-score exceeds the threshold')
    parser.add_argument('--take_profit', type=float, default=20.0,
                       help='Take profit factor (default: 20.0) - Take profit if the unrealized PnL exceeds the factor times the volatility')
    parser.add_argument('--delay', type=float, default=0.0,
                       help='Delay the trade order submission in seconds (default: 0.0) - to avoid different strategies from submitting at the same time')
    parser.add_argument('--strategy', default='trade_zscore',
                       help='Name of the trading strategy function (default: trade_zscore)')

    return parser.parse_args()

# end parse_arguments


# Parse the arguments
args = parse_arguments()

print(f"Trading parameters: symbol={args.symbol}, type={args.type}, "
      f"shares_per_trade={args.shares}, alpha={args.alpha}, "
      f"risk_premium={args.risk_premium}, vol_floor={args.vol_floor}, "
      f"take_profit_factor={args.take_profit}, delay={args.delay}, "
      f"strategy={args.strategy}\n")


if len(sys.argv) > 9:
    symbol = args.symbol
    shares_per_trade = args.shares
    type = args.type
    alpha = args.alpha
    vol_floor = args.vol_floor
    risk_premium = args.risk_premium
    take_profit_factor = args.take_profit
    delay = args.delay
    strategy_function = sys.argv[9].strip().lower()  # Strategy function name
elif len(sys.argv) > 8:
    symbol = args.symbol
    shares_per_trade = args.shares
    type = args.type
    alpha = args.alpha
    vol_floor = args.vol_floor
    risk_premium = args.risk_premium
    take_profit_factor = args.take_profit
    delay = args.delay
    strategy_function = "trade_zscore"  # Default strategy function
elif len(sys.argv) > 7:
    symbol = args.symbol
    shares_per_trade = args.shares
    type = args.type
    alpha = args.alpha
    vol_floor = args.vol_floor
    risk_premium = args.risk_premium
    take_profit_factor = args.take_profit
    delay = args.delay
    strategy_function = "trade_zscore"  # Default strategy function
elif len(sys.argv) > 6:
    symbol = args.symbol
    shares_per_trade = args.shares
    type = args.type
    alpha = args.alpha
    vol_floor = args.vol_floor
    risk_premium = args.risk_premium
    take_profit_factor = 20.0  # Default take profit level
    delay = 0.0  # Default delay (no delay)
    strategy_function = "trade_zscore"  # Default strategy function
elif len(sys.argv) > 5:
    symbol = args.symbol
    shares_per_trade = float(sys.argv[2])  # Number of shares to trade
    type = sys.argv[3].strip().lower()  # Order type (market/limit)
    alpha = float(sys.argv[4])
    vol_floor = float(sys.argv[5])  # Volatility floor
    risk_premium = 2.0  # Default risk_premium value
    take_profit_factor = 20.0  # Default take profit level
    delay = 0.0  # Default delay (no delay)
    strategy_function = "trade_zscore"  # Default strategy function
elif len(sys.argv) > 4:
    symbol = args.symbol
    shares_per_trade = args.shares
    type = args.type
    alpha = args.alpha
    vol_floor = args.vol_floor
    risk_premium = args.risk_premium
    take_profit_factor = args.take_profit
    delay = args.delay
    strategy_function = "trade_zscore"  # Default strategy function
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    type = input("Enter order type (market/limit): ").strip().lower()
    alpha_input = input("Enter EMA alpha parameter (default 0.1): ").strip()
    alpha = float(alpha_input) if alpha_input else 0.1
    risk_premium_input = input("Enter price adjustment (default 0.5): ").strip()
    risk_premium = float(risk_premium_input) if risk_premium_input else 0.5
    vol_floor_input = input("Enter volatility floor (default 0.05): ").strip()
    vol_floor = float(vol_floor_input) if vol_floor_input else 0.05
    take_profit_input = input("Enter take profit level (default 2.0): ").strip()
    take_profit_factor = float(take_profit_input) if take_profit_input else 2.0
    delay_input = input("Enter order submission delay in seconds (default 0.0): ").strip()
    delay = float(delay_input) if delay_input else 0.0
    strategy_function_input = input("Enter strategy function name (default trade_zscore): ").strip()
    strategy_function = strategy_function_input if strategy_function_input else "trade_zscore"

print(f"Trading parameters: symbol={symbol}, type={type}, shares_per_trade={shares_per_trade}, alpha={alpha}, risk_premium={risk_premium}, vol_floor={vol_floor}, take_profit_factor={take_profit_factor}, delay={delay}, strategy_function={strategy_function}\n")


# --------- Initialize the Strategies instance (will be created after getting parameters) --------

# Define the timezone for date/time operations
timezone = ZoneInfo("America/New_York")

# Initialize the Strategies instance with all state variables
# The strategy name, MovAvg, and SDK clients will be created automatically
strategy = CreateStrategy(
    symbol=symbol,
    shares_per_trade=shares_per_trade,
    timezone=timezone,
    type=type,
    alpha=alpha,
    vol_floor=vol_floor,
    risk_premium=risk_premium,
    take_profit_factor=take_profit_factor,
    delay=delay,
    strategy_function=strategy_function,
    env_file="/Users/jerzy/Develop/Python/.env"
)


# --------- Run the WebSocket to handle trade updates and confirmations, and exceptions and Ctrl-C interrupt --------
# --------- Run the data WebSocket stream --------

# Define the main function to run the WebSockets
async def main():

    try:
        # Subscribe to the trade updates and confirms, and handle them using handle_trade_update()
        strategy.alpaca_sdk.get_confirm_stream().subscribe_trade_updates(strategy.handle_trade_update)
        # Run both WebSocket streams concurrently
        print("\nStarting the data WebSocket connection...")
        print("\nStarting the trade updates and confirmations WebSocket connection...")
        await asyncio.gather(
            Bar.stream_bars(symbol, strategy),
            strategy.alpaca_sdk.get_confirm_stream()._run_forever()
        )
    except Exception as e:
        pass  # Handle exceptions here if needed
        # print(f"WebSocket error: {e}")
    finally:
        print("\nClosing the trade updates and confirmations WebSocket connection...")
        try:
            # await data_client.close()
            await strategy.alpaca_sdk.get_confirm_stream().close()
        except:
            pass  # Ignore errors when closing


# Check whether the script is being run directly or is imported as a module
if __name__ == "__main__":
    # Perform simplified event loop handling
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot be called from a running event loop" in str(e):
            print("Running in existing event loop/Users/jerzy/Develop/Python/.environment...")
            # Create a task in the existing loop
            loop = asyncio.get_event_loop()
            task = loop.create_task(main())
            # You might need to await this task manually in Jupyter
        else:
            # Suppress traceback for other RuntimeErrors
            print(f"Runtime error: {str(e)}")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        # Suppress full traceback, just show error message
        print(f"Error occurred: {str(e)}")

