"""
MachineTrader Package
A comprehensive trading framework for algorithmic trading strategies.

Note: The Bar class has been moved to the TechIndic package.
The stream_bars function is available in the AlpacaSDK package.
"""

from .trading import SingleStrategy, GetArgs, BaseStrategy, StrategyFactory

# Backward compatibility alias
CreateStrategy = StrategyFactory.create

__version__ = "1.0.0"
__all__ = ["SingleStrategy", "GetArgs", "BaseStrategy", "StrategyFactory", "CreateStrategy"]
