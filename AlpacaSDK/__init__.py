"""
AlpacaSDK package - Alpaca trading utility functions.

This package provides the AlpacaSDK class for object-oriented Alpaca API interactions:
- AlpacaSDK: Complete object-oriented interface for all Alpaca operations
  - create_trade_clients: Initialize trading and confirmation stream clients  
  - create_data_client: Initialize data client for historical market data
  - get_trading_client: Access trading client instance
  - get_confirm_stream: Access confirmation stream instance
  - get_data_client: Access data client instance
  - get_position: Get open position for a symbol
  - cancel_orders: Cancel orders for a symbol
  - submit_order: Submit trading orders
- Bar: Price bar representation class for WebSocket data handling
  - Converts dictionary data to bar objects with Alpaca-compatible format
  - Provides save_bar method for CSV export
  - Includes stream_bars static method for WebSocket streaming

MIGRATION NOTE: The function-based API has been deprecated in favor of AlpacaSDK class.
"""

from .alpacasdk import AlpacaSDK

__all__ = [
    'AlpacaSDK'
]
