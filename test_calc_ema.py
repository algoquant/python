"""
Calculate the Exponential Moving Average with persistent state using a MovAvg class.
Uses the package TechIndic.

Run the code in the terminal:
    python3 calc_ema_test.py 0.9

"""

import sys
from TechIndic import MovAvg, IndicatorFactory


# Example usage:
if __name__ == "__main__":
    # Get alpha from command line arguments
    if len(sys.argv) > 1:
        alpha = float(sys.argv[1])
    else:
        alpha = 0.9  # Default 90% smoothing factor
    
    print(f"Using alpha = {alpha}")
    
    # Test parameters
    vol_floor = 0.01  # Default volatility floor
    
    # Test the persistent EMA function using factory method
    print("Creating MovAvg instance using IndicatorFactory...")
    
    # Method 1: Using factory method (recommended approach)
    mov_avg_factory = IndicatorFactory.create('MovAvg', alpha=alpha, vol_floor=vol_floor)
    print(f"Factory-created instance: {type(mov_avg_factory).__name__}")
    
    # Method 2: Direct instantiation (traditional approach)
    mov_avg_direct = MovAvg(alpha=alpha, vol_floor=vol_floor)
    print(f"Direct-created instance: {type(mov_avg_direct).__name__}")
    
    # Use the factory-created instance for testing
    mov_avg = mov_avg_factory

    # Sample price data
    prices = [100.0, 102.0, 98.0, 105.0, 103.0, 99.0, 101.0, 104.0, 97.0, 106.0]
    volumes = [100.0, 200.0, 100.0, 200.0, 150.0, 100.0, 120.0, 180.0, 90.0, 200.0]

    """
    print("Testing calc_ema:")
    print("Calculate the EMA price.")
    print("Price\tEMA")
    print("-" * 15)
    for price in prices:
        ema = mov_avg.calc_ema(price)
        print(f"{price:.1f}\t{ema:.2f}")
    """

    print("\nTesting calc_zscore:")
    print("Calculate the Z-score from the EMA price and variance.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price in prices:
        zscore, ema, vol = mov_avg.calc_zscore(price)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """

    print("\nTesting calc_zscorew:")
    print("Calculate the Z-score from the EMA price and variance weighted by the trading volumes.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price, volume in zip(prices, volumes):
        zscore, ema, vol = mov_avg.calc_zscorew(price, volume)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """
