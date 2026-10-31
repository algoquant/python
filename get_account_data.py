"""
Account Data Script - Downloads brokerage account information every minute into a CSV file.

This script continuously monitors your Alpaca brokerage account and logs key account metrics
to a CSV file with timestamps. It captures account value, buying power, positions, and other
important account statistics.

Usage:
    python3 get_account_data.py

The script will run continuously until stopped with Ctrl+C.
Data is saved to: account_data_YYYYMMDD.csv

Account metrics captured:
- Account value (equity)
- Buying power
- Cash available
- Portfolio value
- Day trade buying power
- Pattern day trader status
- Number of positions
- Account status
- Timestamp

Press Ctrl+C to stop the monitoring.
"""

import os
import sys
import time
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from alpaca.trading.requests import GetAssetsRequest
from MachineTrader.helpers.alpacasdk import AlpacAPI

# --------- Configuration --------

# Data directory
DATA_DIR = os.getenv("DATA_DIR_NAME") or "./"

# Time zone
TIMEZONE = ZoneInfo("America/New_York")

# Update interval (seconds) - 60 seconds = 1 minute
UPDATE_INTERVAL = 60

# --------- Create the SDK client --------

# Create the SDK trading client
alpaca_sdk = AlpacAPI()
alpaca_sdk.create_trade_clients()
trading_client = alpaca_sdk.get_trading_client()

# --------- Create file name --------

def get_filename():
    """Generate filename with current date"""
    date_str = datetime.now(TIMEZONE).strftime("%Y%m%d")
    return f"{DATA_DIR}account_data_{date_str}.csv"

# --------- Get account information --------

def get_account_data():
    """Fetch account information and return as dictionary"""
    try:
        # Get account information
        account = trading_client.get_account()
        
        # Get all positions
        positions = trading_client.get_all_positions()
        
        # Prepare account data
        account_data = {
            "timestamp": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
            "account_number": account.account_number,
            "status": account.status,
            "currency": account.currency,
            "buying_power": float(account.buying_power),
            "regt_buying_power": float(account.regt_buying_power),
            "daytrading_buying_power": float(account.daytrading_buying_power),
            "non_marginable_buying_power": float(account.non_marginable_buying_power),
            "cash": float(account.cash),
            "accrued_fees": float(account.accrued_fees),
            "pending_transfer_out": float(account.pending_transfer_out) if account.pending_transfer_out else 0.0,
            "pending_transfer_in": float(account.pending_transfer_in) if account.pending_transfer_in else 0.0,
            "portfolio_value": float(account.portfolio_value),
            "pattern_day_trader": account.pattern_day_trader,
            "trading_blocked": account.trading_blocked,
            "transfers_blocked": account.transfers_blocked,
            "account_blocked": account.account_blocked,
            "created_at": account.created_at.strftime("%Y-%m-%d %H:%M:%S") if account.created_at else None,
            "trade_suspended_by_user": account.trade_suspended_by_user,
            "multiplier": account.multiplier,
            "shorting_enabled": account.shorting_enabled,
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "long_market_value": float(account.long_market_value) if account.long_market_value else 0.0,
            "short_market_value": float(account.short_market_value) if account.short_market_value else 0.0,
            "initial_margin": float(account.initial_margin) if account.initial_margin else 0.0,
            "maintenance_margin": float(account.maintenance_margin) if account.maintenance_margin else 0.0,
            "last_maintenance_margin": float(account.last_maintenance_margin) if account.last_maintenance_margin else 0.0,
            "sma": float(account.sma) if account.sma else 0.0,
            "daytrade_count": account.daytrade_count,
            "num_positions": len(positions),
            "total_position_value": sum(float(pos.market_value) if pos.market_value else 0.0 for pos in positions),
            "unrealized_pl": sum(float(pos.unrealized_pl) if pos.unrealized_pl else 0.0 for pos in positions),
            "unrealized_plpc": sum(float(pos.unrealized_plpc) if pos.unrealized_plpc else 0.0 for pos in positions) / len(positions) if positions else 0.0,
        }
        
        return account_data
        
    except Exception as e:
        print(f"❌ Error fetching account data: {e}")
        return None

# --------- Save data to CSV --------

def save_to_csv(data):
    """Save account data to CSV file"""
    try:
        filename = get_filename()
        df = pd.DataFrame([data])
        
        # Check if file exists to determine if header should be written
        file_exists = os.path.exists(filename)
        
        # Append to CSV
        df.to_csv(filename, mode="a", header=not file_exists, index=False)
        
        return filename
        
    except Exception as e:
        print(f"❌ Error saving to CSV: {e}")
        return None

# --------- Main monitoring loop --------

def main():
    """Main monitoring loop"""
    print("🚀 Starting Account Monitor...")
    print(f"📊 Data will be saved to: {get_filename()}")
    print(f"⏱️ Update interval: {UPDATE_INTERVAL} seconds")
    print(f"🕐 Time zone: {TIMEZONE}")
    print("Press Ctrl+C to stop monitoring\n")
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            start_time = time.time()
            
            print(f"📈 Iteration {iteration}: Fetching account data...")
            
            # Get account data
            account_data = get_account_data()
            
            if account_data:
                # Save to CSV
                filename = save_to_csv(account_data)
                
                if filename:
                    print(f"✅ Account data saved to {filename}")
                    print(f"💰 Portfolio Value: ${account_data['portfolio_value']:,.2f}")
                    print(f"💵 Cash: ${account_data['cash']:,.2f}")
                    print(f"📊 Buying Power: ${account_data['buying_power']:,.2f}")
                    print(f"📈 Positions: {account_data['num_positions']}")
                    print(f"💹 Unrealized P&L: ${account_data['unrealized_pl']:,.2f}")
                else:
                    print("❌ Failed to save account data")
            else:
                print("❌ Failed to fetch account data")
            
            # Calculate sleep time to maintain exact interval
            elapsed_time = time.time() - start_time
            sleep_time = max(0, UPDATE_INTERVAL - elapsed_time)
            
            if sleep_time > 0:
                print(f"⏳ Waiting {sleep_time:.1f} seconds until next update...\n")
                time.sleep(sleep_time)
            else:
                print("⚠️ Warning: Data collection took longer than update interval\n")
                
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        print(f"📁 Data saved in: {get_filename()}")
        print("✨ Account monitoring completed")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

# --------- Entry point --------

if __name__ == "__main__":
    main()
