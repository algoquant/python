# Calculate the Exponential Moving Average with persistent state using an EMA class

from utils import EMACalculator


# Example usage:
if __name__ == "__main__":
    # Test the persistent EMA function
    alpha = 0.9  # 90% smoothing factor

    # Sample price data
    prices = [100.0, 102.0, 98.0, 105.0, 103.0, 99.0, 101.0, 104.0, 97.0, 106.0]
    volumes = [100.0, 200.0, 100.0, 200.0, 150.0, 100.0, 120.0, 180.0, 90.0, 200.0]

    # Create an instance of the EMACalculator
    EMAC = EMACalculator()

    """
    print("Testing calc_ema:")
    print("Calculate the EMA price.")
    print("Price\tEMA")
    print("-" * 15)
    for price in prices:
        ema = EMAC.calc_ema(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")
    """

    print("\nTesting calc_zscore:")
    print("Calculate the Z-score from the EMA price and variance.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price in prices:
        zscore, ema, vol = EMAC.calc_zscore(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """

    print("\nTesting calc_zscorew:")
    print("Calculate the Z-score from the EMA price and variance weighted by the trading volumes.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price, volume in zip(prices, volumes):
        zscore, ema, vol = EMAC.calc_zscorew(price, volume, alpha)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    """
