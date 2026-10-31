"""
Download a time series of historical portfolio values from Alpaca.

This script gets historical portfolio performance data from your Alpaca account,
including portfolio value, profit/loss, equity, and other key metrics over time.

Usage:
    python3 get_account_history.py [period] [timeframe]

Arguments:
    period: Time period for historical data (1M, 3M, 6M, 1A, 2A, 5A, all)
    timeframe: Data frequency (1Min, 5Min, 15Min, 1H, 1D)

Examples:
    python3 get_account_history.py 1A 1D    # Last year, daily data
    python3 get_account_history.py 6M 1H    # Last 6 months, hourly data
    python3 get_account_history.py all 1D   # All available data, daily

Default: 1A (1 year) with 1D (daily) timeframe

Portfolio metrics downloaded:
- Timestamp
- Equity (total portfolio value)
- Profit/Loss (dollar amount)
- Profit/Loss percentage
- Base value (initial portfolio value)
- Timeframe period
- Number of data points

Data is saved to: portfolio_history_YYYYMMDD_HHMMSS.csv
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from alpaca.trading.requests import GetPortfolioHistoryRequest
from MachineTrader.helpers.alpacasdk import AlpacAPI

# --------- Configuration --------

# Data directory
DATA_DIR = os.getenv("DATA_DIR_NAME") or "./"

# Time zone
TIMEZONE = ZoneInfo("America/New_York")

# --------- Validation --------

# --------- Create the SDK client --------

# Create the SDK trading client
alpaca_sdk = AlpacAPI()
alpaca_sdk.create_trade_clients()
trading_client = alpaca_sdk.get_trading_client()

# --------- Parse command line arguments --------

def parse_arguments():
    """Parse command line arguments with defaults"""
    
    # Default values
    default_period = "1A"  # 1 year
    default_timeframe = "1D"  # Daily
    
    # Available periods (use string values directly)
    valid_periods = {
        "1D": "1D",
        "7D": "7D", 
        "1M": "1M",
        "3M": "3M",
        "6M": "6M",
        "1A": "1A",
        "2A": "2A",
        "5A": "5A",
        "all": "all"
    }
    
    # Available timeframes (use string values directly)
    valid_timeframes = {
        "1Min": "1Min",
        "5Min": "5Min",
        "15Min": "15Min",
        "1H": "1H",
        "1D": "1D"
    }
    
    # Parse arguments
    if len(sys.argv) > 1:
        period_str = sys.argv[1].upper()
        if period_str not in valid_periods:
            print(f"❌ Invalid period: {period_str}")
            print(f"Valid periods: {', '.join(valid_periods.keys())}")
            sys.exit(1)
        period = valid_periods[period_str]
    else:
        period_str = default_period
        period = valid_periods[default_period]
    
    if len(sys.argv) > 2:
        timeframe_str = sys.argv[2]
        if timeframe_str not in valid_timeframes:
            print(f"❌ Invalid timeframe: {timeframe_str}")
            print(f"Valid timeframes: {', '.join(valid_timeframes.keys())}")
            sys.exit(1)
        timeframe = valid_timeframes[timeframe_str]
    else:
        timeframe_str = default_timeframe
        timeframe = valid_timeframes[default_timeframe]
    
    return period, timeframe, period_str, timeframe_str

# --------- Generate filename --------

def generate_filename(period_str, timeframe_str):
    """Generate filename with timestamp and parameters"""
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    return f"{DATA_DIR}portfolio_history_{period_str}_{timeframe_str}_{timestamp}.csv"

# --------- Fetch portfolio history --------

def fetch_portfolio_history(period, timeframe):
    """Fetch portfolio history from Alpaca"""
    try:
        print("📊 Fetching portfolio history from Alpaca...")
        
        # Create request with string parameters
        request = GetPortfolioHistoryRequest(
            period=period,
            timeframe=timeframe,
            extended_hours=True  # Include extended hours data
        )
        
        # Get portfolio history
        portfolio_history = trading_client.get_portfolio_history(request)
        
        return portfolio_history
        
    except Exception as e:
        print(f"❌ Error fetching portfolio history: {e}")
        return None

# --------- Process portfolio data --------

def process_portfolio_data(portfolio_history):
    """Process portfolio history data into DataFrame"""
    try:
        print("🔄 Processing portfolio data...")
        
        # Extract data
        timestamps = portfolio_history.timestamp
        equity = portfolio_history.equity
        profit_loss = portfolio_history.profit_loss
        profit_loss_pct = portfolio_history.profit_loss_pct
        base_value = portfolio_history.base_value
        timeframe = portfolio_history.timeframe
        
        # Convert timestamps to readable format
        readable_timestamps = []
        for ts in timestamps:
            if ts:
                # Convert from milliseconds to seconds and create datetime
                dt = datetime.fromtimestamp(ts, tz=TIMEZONE)
                readable_timestamps.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                readable_timestamps.append(None)
        
        # Create DataFrame
        data = {
            "timestamp": readable_timestamps,
            "timestamp_unix": timestamps,
            "equity": equity,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "base_value": [base_value] * len(timestamps) if base_value else [None] * len(timestamps),
            "timeframe": [timeframe] * len(timestamps) if timeframe else [None] * len(timestamps),
        }
        
        # Remove None entries
        df = pd.DataFrame(data)
        df = df.dropna(subset=['timestamp'])
        
        # Add calculated fields
        if len(df) > 0:
            df['returns_pct'] = df['equity'].pct_change() * 100
            df['cumulative_returns_pct'] = ((df['equity'] / df['equity'].iloc[0]) - 1) * 100
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.day_name()
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        
        return df
        
    except Exception as e:
        print(f"❌ Error processing portfolio data: {e}")
        return None

# --------- Save to CSV --------

def save_to_csv(df, filename):
    """Save DataFrame to CSV file"""
    try:
        df.to_csv(filename, index=False)
        return True
    except Exception as e:
        print(f"❌ Error saving to CSV: {e}")
        return False

# --------- Display summary --------

def display_summary(df, period_str, timeframe_str):
    """Display summary statistics"""
    try:
        print("\n📈 Portfolio History Summary:")
        print(f"Period: {period_str}, Timeframe: {timeframe_str}")
        print(f"Data Points: {len(df)}")
        
        if len(df) > 0:
            print(f"Date Range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
            
            # Current values
            current_equity = df['equity'].iloc[-1]
            initial_equity = df['equity'].iloc[0]
            total_return_pct = ((current_equity / initial_equity) - 1) * 100
            
            print(f"💰 Initial Equity: ${initial_equity:,.2f}")
            print(f"💰 Current Equity: ${current_equity:,.2f}")
            print(f"📊 Total Return: {total_return_pct:+.2f}%")
            
            # Profit/Loss info
            if df['profit_loss'].notna().any():
                current_pl = df['profit_loss'].iloc[-1]
                print(f"💹 Current P&L: ${current_pl:+,.2f}")
            
            if df['profit_loss_pct'].notna().any():
                current_pl_pct = df['profit_loss_pct'].iloc[-1]
                print(f"📈 Current P&L %: {current_pl_pct:+.2f}%")
            
            # Volatility metrics
            if len(df) > 1:
                daily_returns = df['returns_pct'].dropna()
                if len(daily_returns) > 0:
                    volatility = daily_returns.std()
                    max_drawdown = (df['equity'] / df['equity'].cummax() - 1).min() * 100
                    print(f"📊 Return Volatility: {volatility:.2f}%")
                    print(f"📉 Max Drawdown: {max_drawdown:.2f}%")
        
    except Exception as e:
        print(f"❌ Error displaying summary: {e}")

# --------- Main function --------

def main():
    """Main function"""
    print("🚀 Starting Portfolio History Downloader...")
    
    # Parse arguments
    period, timeframe, period_str, timeframe_str = parse_arguments()
    
    print(f"📅 Period: {period_str}")
    print(f"⏱️ Timeframe: {timeframe_str}")
    
    # Generate filename
    filename = generate_filename(period_str, timeframe_str)
    print(f"📁 Output file: {filename}")
    
    # Fetch portfolio history
    portfolio_history = fetch_portfolio_history(period, timeframe)
    
    if portfolio_history is None:
        print("❌ Failed to fetch portfolio history")
        return
    
    # Process data
    df = process_portfolio_data(portfolio_history)
    
    if df is None or len(df) == 0:
        print("❌ No portfolio data to process")
        return
    
    # Save to CSV
    if save_to_csv(df, filename):
        print(f"✅ Portfolio history saved to: {filename}")
        
        # Display summary
        display_summary(df, period_str, timeframe_str)
        
        print(f"\n📊 CSV columns: {', '.join(df.columns)}")
        print("✨ Download completed successfully!")
        
    else:
        print("❌ Failed to save portfolio history")

# --------- Entry point --------

if __name__ == "__main__":
    main()
