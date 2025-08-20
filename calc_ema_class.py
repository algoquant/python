# Calculate the Exponential Moving Average with persistent state using an EMA class

"""
EMACalculator: Calculate the Exponential Moving Average EMA with persistent state.

Methods:
    calc_ema(current_price, alpha): Calculate and update EMA
    calc_zscore(current_price, alpha, vol_floor): Calculate z-score with persistent state
    calc_zscorew(current_price, alpha, volume, vol_floor): Calculate z-score with EMA weighted by volumes
    reset(): Reset the EMA state

Args:
    current_price (float): The latest price value
    alpha (float): Smoothing factor (0 < alpha <= 1)
    volume (float): Trading volume for the current price
    vol_floor (float): Minimum volatility to avoid division by zero

Returns:
    float: Updated EMA value

Updating formulas:
EMA = α × EMA + (1-α) × current_price
Weighted EMA: EMAw = α × EMAw + (1-α) × volume × current_price
EMA volume: EMAvolume = α × EMAvolume + (1-α) × volume
EMA scaled: EMA = EMAw / EMAvolume

"""


class EMACalculator:

    def __init__(self):
        self.ema_price = None
        self.alpha1 = None
        self.price_var = None
        self.alpha_squared = None
        self.alpha2 = None
    
    def reset(self):
        """Reset the EMA state"""
        self.ema_price = None
        self.alpha1 = None
        self.price_var = None
        self.alpha_squared = None
        self.alpha2 = None


    """
    Calculate the EMA price using a persistent state.
    Returns: (ema_price)
    """
    def calc_ema(self, current_price, alpha):

        if self.ema_price is None:
            # Initialize EMA with first price
            self.ema_price = current_price
            self.alpha1 = 1 - alpha  # Store for efficiency
        else:
            # Update the EMA: EMA = alpha * previous_EMA + (1 - alpha) * current_price
            self.ema_price = alpha * self.ema_price + self.alpha1 * current_price
        
        return self.ema_price
    # end of calc_ema method


    """
    Calculate the Z-score from the EMA price and variance.
    Returns: (zscore, ema_price, price_vol)
    """
    def calc_zscore(self, current_price, alpha, vol_floor=0.01):

        if self.ema_price is None:
            # Initialize on first call
            self.ema_price = current_price  # Start with current price
            self.price_var = vol_floor  # Start with floor variance
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            # First call returns zero z-score
            return 0.0, self.ema_price, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = current_price - self.ema_price
            
            # Calculate the volatility as the square root of variance with vol_floor
            price_vol = max(self.price_var ** 0.5, vol_floor)
            
            # Calculate the Z-score
            zscore = price_deviation / price_vol

            # Update the EMA variance
            self.price_var = self.alpha_squared * self.price_var + self.alpha2 * (price_deviation * price_deviation)

            # Update the EMA price
            self.ema_price = alpha * self.ema_price + self.alpha1 * current_price
            
            return zscore, self.ema_price, price_vol

    # end of calc_zscore method


    """
    Calculate the Z-score from the EMA price and variance weighted by the trading volumes.
    Returns: (zscore, ema_price, price_vol)
    """
    def calc_zscorew(self, current_price, alpha, volume, vol_floor=0.01):

        if self.ema_price is None:
            # Initialize on first call
            self.ema_price = volume * current_price  # Start with current price times volume
            self.price_var = volume * vol_floor * vol_floor  # Start with floor variance times volume
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.volume = volume  # Initialize the volume to avoid division by zero
            # First call returns zero z-score
            return 0.0, self.ema_price / self.volume, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = current_price - self.ema_price / self.volume

            # Calculate the volatility as the square root of variance with vol_floor
            price_vol = max((self.price_var / self.volume) ** 0.5, vol_floor)  # Normalize by volume

            # Calculate the Z-score
            zscore = price_deviation / price_vol

            # Update the EMA volume
            self.volume = alpha * self.volume + self.alpha1 * volume

            # Update the EMA variance
            self.price_var = self.alpha_squared * self.price_var + self.alpha2 * volume * (price_deviation * price_deviation)

            # Update the EMA price
            self.ema_price = alpha * self.ema_price + self.alpha1 * volume * current_price
            ema_price = self.ema_price / self.volume  # Normalize by volume

            return zscore, ema_price, price_vol

    # end of calc_zscorew method


# end of EMACalculator class



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
    print("Price\tEMA")
    print("-" * 15)
    for price in prices:
        ema = EMAC.calc_ema(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")

    print("\nTesting calc_zscore:")
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
        zscore, ema, vol = EMAC.calc_zscorew(price, alpha, volume)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

