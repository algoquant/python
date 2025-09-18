"""
Calculate the Exponential Moving Average with persistent state using a MovAvg class.
Uses the package TechIndic.

Run the code in the terminal:
    python3 calc_ema_test.py 0.9

"""

import sys
from TechIndic import MovAvg


# Example usage:
if __name__ == "__main__":
    # Get alpha from command line arguments
    if len(sys.argv) > 1:
        alpha = float(sys.argv[1])
    else:
        alpha = 0.9  # Default 90% smoothing factor
    
    print(f"Using alpha = {alpha}")
    
    # Test the persistent EMA function

    # Sample price data
    prices = [100.0, 102.0, 98.0, 105.0, 103.0, 99.0, 101.0, 104.0, 97.0, 106.0]
    volumes = [100.0, 200.0, 100.0, 200.0, 150.0, 100.0, 120.0, 180.0, 90.0, 200.0]

    # Create an instance of the MovAvg
    mov_avg = MovAvg()

    """
    print("Testing calc_ema:")
    print("Calculate the EMA price.")
    print("Price\tEMA")
    print("-" * 15)
    for price in prices:
        ema = mov_avg.calc_ema(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")
    """

    print("\nTesting calc_zscore:")
    print("Calculate the Z-score from the EMA price and variance.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price in prices:
        zscore, ema, vol = mov_avg.calc_zscore(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """

    print("\nTesting calc_zscorew:")
    print("Calculate the Z-score from the EMA price and variance weighted by the trading volumes.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price, volume in zip(prices, volumes):
        zscore, ema, vol = mov_avg.calc_zscorew(price, volume, alpha)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """
