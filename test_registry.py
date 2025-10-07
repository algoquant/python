#!/usr/bin/env python3
"""
Quick test to check what's in the IndicatorFactory registry.
"""

from TechIndic import IndicatorFactory

print("IndicatorFactory registry contents:")
registry = IndicatorFactory._indicators
for name, cls in registry.items():
    print(f"  {name}: {cls}")

print(f"\nGet available indicators: {IndicatorFactory.get_available_indicators()}")
