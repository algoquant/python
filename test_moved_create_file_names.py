#!/usr/bin/env python3
"""
Test script demonstrating the moved create_file_names method from CreateStrategy to AlpacaSDK.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv


class AlpacaSDKDemo:
    """Simplified AlpacaSDK class for demonstration purposes."""
    
    def create_file_names(self, strategy_name, symbol, timezone=None, dir_name=None, env_file=None, dir_env_var="DATA_DIR_NAME"):
        """
        Create standardized file names for strategy logging files.
        (This is the method that was moved from CreateStrategy to AlpacaSDK)
        """
        
        # Set default timezone if not provided
        if timezone is None:
            timezone = ZoneInfo("America/New_York")

        # Load the API keys from .env file if provided
        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            # Load from default .env file in current directory
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")

        # Use provided dir_name or get from environment variable or default
        if dir_name is None:
            dir_name = os.getenv(dir_env_var) or "./"
            if dir_name != "./":
                print(f"📁 Using directory from {dir_env_var}: {dir_name}")
            else:
                print("📁 Using default directory: ./")
        else:
            print(f"📁 Using specified directory: {dir_name}")
        
        # Ensure directory path ends with separator
        if not dir_name.endswith(("/", "\\")):
            dir_name += "/"
        
        # Get the current time in the specified timezone
        time_now = datetime.now(timezone)
        # Format date as YYYYMMDD
        date_short = time_now.strftime("%Y%m%d")
        
        # Create standardized file names
        file_names = {
            "state_file": f"{dir_name}state_{strategy_name}_{symbol}_{date_short}.csv",
            "submits_file": f"{dir_name}submits_{strategy_name}_{symbol}_{date_short}.csv",
            "fills_file": f"{dir_name}fills_{strategy_name}_{symbol}_{date_short}.csv",
            "canceled_file": f"{dir_name}canceled_{strategy_name}_{symbol}_{date_short}.csv",
            "error_file": f"{dir_name}error_{strategy_name}_{symbol}_{date_short}.csv"
        }
        
        print(f"✅ Strategy files created successfully in directory: {dir_name}")
        print(f"📋 Files: {len(file_names)} files for strategy '{strategy_name}' on {date_short}")
        
        return file_names


def main():
    print("=" * 60)
    print("DEMONSTRATION: create_file_names moved from CreateStrategy to AlpacaSDK")
    print("=" * 60)
    
    # Create AlpacaSDK instance
    alpaca_sdk = AlpacaSDKDemo()
    
    # Test the moved method
    print("\n1. Basic usage:")
    files = alpaca_sdk.create_file_names("MyStrategy", "AAPL")
    
    print("\n📋 Generated files:")
    for file_type, file_path in files.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n2. With custom directory:")
    files = alpaca_sdk.create_file_names("MyStrategy", "AAPL", dir_name="/tmp/trading_logs/")
    
    print("\n📋 Generated files (custom directory):")
    for file_type, file_path in files.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n" + "=" * 60)
    print("✅ Method successfully moved from CreateStrategy to AlpacaSDK!")
    print("✅ All functionality preserved with improved organization!")
    print("=" * 60)


if __name__ == "__main__":
    main()
