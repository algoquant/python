# Calculate the Exponential Moving Average with persistent state using an EMA class

"""
EMACalculator: Calculate the Exponential Moving Average EMA with persistent state.

Methods:
    calc_ema_price(price_current, alpha): Calculate and update EMA
    calc_zscore_price(price_current, alpha, vol_floor): Calculate z-score with persistent state
    calc_zscore_price_weighted(price_current, alpha, volume, vol_floor): Calculate z-score with EMA weighted by volumes
    calc_zscore_open(price_current, price_ema, alpha, volume, vol_floor): Calculate open-reference z-score with return volatility weighted by volumes
    calc_ret_ema(price_current, alpha): Calculate and update EMA of stock returns
    calc_zscore_return(price_current, alpha, vol_floor): Calculate return z-score with persistent state
    reset(): Reset the EMA state

Args:
    price_current (float): The latest price value
    alpha (float): Smoothing factor (0 < alpha <= 1)
    volume (float): Trading volume for the current price
    vol_floor (float): Minimum volatility to avoid division by zero

Returns:
    float: Updated EMA value

Updating formulas:
EMA = α × EMA + (1-α) × price_current
Weighted EMA: EMAw = α × EMAw + (1-α) × volume × price_current
EMA volume: vol_ema = α × vol_ema + (1-α) × volume
EMA scaled: EMA = EMAw / vol_ema
Return deviation: return = price_current - price_previous

"""

import math

# Minimum value of volume to avoid division by zero or extremely small numbers
volume_floor = 1


def _is_na_price(value) -> bool:
    """True when a price input is missing/NaN, used to short-circuit z-score updates on NA bars."""
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


class EMACalculator:

    def __init__(self):
        self.price_ema = None
        self.alpha1 = None
        self.var_emaw = None
        self.alpha_squared = None
        self.alpha2 = None
        self.vol_ema = None
        self.price_previous = None
        self.price_diff_sign = 0
        self.ret_emaw = None
        self.var_emaw = None
        self.vol_ema = None
        self.return_alpha1 = None
        self.alpha_squared = None
        self.alpha2 = None
    
    def reset(self):
        """Reset the EMA state"""
        self.price_ema = None
        self.alpha1 = None
        self.var_emaw = None
        self.alpha_squared = None
        self.alpha2 = None
        self.vol_ema = None
        self.price_previous = None
        self.price_diff_sign = 0
        self.ret_emaw = None
        self.var_emaw = None
        self.vol_ema = None
        self.return_alpha1 = None
        self.alpha_squared = None
        self.alpha2 = None


    """
    Calculate the EMA price using a persistent state.
    Returns: (price_ema)
    """
    def calc_ema_price(self, price_current, alpha):

        if self.price_ema is None:
            # Initialize EMA with first price
            self.price_ema = price_current
            self.alpha1 = 1 - alpha  # Store for efficiency
        else:
            # Update the EMA: EMA = alpha * previous_EMA + (1 - alpha) * price_current
            self.price_ema = alpha * self.price_ema + self.alpha1 * price_current
        
        return self.price_ema
    # end of calc_ema_price method


    """
    Calculate the EMA of stock returns using a persistent state.
    Returns: (ret_ema)
    """
    def calc_ret_ema(self, price_current, alpha):

        if self.price_previous is None:
            self.price_previous = price_current
            self.ret_emaw = 0.0
            self.return_alpha1 = 1 - alpha
            return self.ret_emaw

        price_diff = price_current - self.price_previous

        if self.ret_emaw is None:
            self.ret_emaw = price_diff
            self.return_alpha1 = 1 - alpha
        else:
            self.ret_emaw = alpha * self.ret_emaw + self.return_alpha1 * price_diff

        self.price_previous = price_current
        return self.ret_emaw
    # end of calc_ret_ema method


    """
    Calculate the Z-score from the EMA price and the price variance.
    Returns: (zscore, price_ema, price_vol)
    """
    def calc_zscore_price(self, price_current, alpha, vol_floor=0.5):

        if _is_na_price(price_current):
            if self.price_ema is None:
                return 0.0, None, vol_floor
            price_vol = max(max(float(self.var_emaw), 0.0) ** 0.5, vol_floor)
            return 0.0, self.price_ema, price_vol

        if self.price_ema is None:
            # Initialize on first call
            self.price_ema = price_current  # Start with current price
            self.var_emaw = vol_floor  # Start with floor variance
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            # First call returns zero z-score
            return 0.0, price_current, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = price_current - self.price_ema
            
            # Enforce volatility floor greater than price deviation
            safe_var = max(float(self.var_emaw), 0.0)
            price_vol = safe_var ** 0.5
            price_vol = max(price_vol, vol_floor)
            # price_vol = max(price_vol, vol_floor, abs(price_deviation))
            
            # Calculate the Z-score
            zscore = price_deviation / price_vol

            # Update the EMA variance
            self.var_emaw = self.alpha_squared * self.var_emaw + self.alpha2 * (price_deviation * price_deviation)

            # Update the EMA price
            self.price_ema = alpha * self.price_ema + self.alpha1 * price_current
            
            return zscore, self.price_ema, price_vol

    # end of calc_zscore_price method


    """
    Calculate the Z-score from the EMA return and the return variance.
    Returns: (zscore, ret_ema, volat_ema)
    """
    def calc_zscore_return(self, price_current, alpha, vol_floor=0.5):

        if _is_na_price(price_current):
            if self.ret_emaw is None or self.var_emaw is None:
                return 0.0, 0.0, vol_floor
            volat_ema = max(max(float(self.var_emaw), 0.0) ** 0.5, vol_floor)
            return 0.0, self.ret_emaw, volat_ema

        if self.price_previous is None or self.ret_emaw is None or self.var_emaw is None:
            self.price_previous = price_current
            self.ret_emaw = 0.0
            self.var_emaw = vol_floor * vol_floor
            self.return_alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            return 0.0, self.ret_emaw, vol_floor

        price_diff = price_current - self.price_previous

        safe_var = max(float(self.var_emaw), 0.0)
        volat_ema = safe_var ** 0.5
        volat_ema = max(volat_ema, vol_floor)
        # volat_ema = max(volat_ema, vol_floor, abs(price_diff))

        zscore = price_diff / volat_ema

        self.var_emaw = self.alpha_squared * self.var_emaw + self.alpha2 * (price_diff * price_diff)
        self.ret_emaw = alpha * self.ret_emaw + self.return_alpha1 * price_diff
        self.price_previous = price_current

        return zscore, self.ret_emaw, volat_ema

    # end of calc_zscore_return method


    """
    Calculate the Z-score from the EMA price and the price variance weighted by the trading volumes.
    Returns: (zscore, price_ema, price_vol)
    """
    def calc_zscore_price_weighted(self, price_current, alpha, volume, vol_floor=0.5):

        # Handle invalid NA price.
        if _is_na_price(price_current):
            if any(value is None for value in (self.zscore, self.price_ema, self.volat_ema)):
                # Has not been initialized, return default values.
                return 0.0, 0.0, vol_floor
            else:
                # Has been initialized, return previous EMA values.
                return self.zscore, self.price_ema, self.volat_ema

        # Initialize for the first valid price.
        if any(value is None for value in (self.price_previous, self.zscore, self.price_ema, self.volat_ema)):
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.price_previous = price_current
            self.price_ema = price_current  # Initialize EMA price with current price
            self.price_emaw = volume * price_current  # Initialize weighted EMA price with current price times volume
            self.volat_ema = vol_floor  # Initialize the volatility EMA
            self.var_emaw = volume * vol_floor * vol_floor
            self.vol_ema = volume  # Initialize the EMA volume
            # First call returns zero z-score
            self.zscore = 0.0
            return self.zscore, self.price_ema, self.volat_ema

        # Calculate the price deviation from the current EMA
        price_deviation = price_current - self.price_ema
        # price_diff = price_current - self.price_previous
        self.price_previous = price_current

        # Update the EMA price and variance (volatility)
        # Use VWAP for near-1 alpha, otherwise keep EMA update.
        if alpha >= 0.999:
            # Update the EMA volume
            self.vol_ema = self.vol_ema + volume
            # Update the EMA price
            self.price_emaw = self.price_emaw + volume * price_current
            self.price_ema = self.price_emaw / self.vol_ema
            # Update the EMM variance (volatility)
            diff_squared = price_deviation * price_deviation
            self.var_emaw = self.var_emaw + volume * diff_squared
            # Set the variance to be at least as large as the current squared deviation
            self.var_emaw = max(self.vol_ema * diff_squared, self.var_emaw)
            # Enforce the minimum volatility floor
            var_ema = self.var_emaw / self.vol_ema
            self.volat_ema = max(var_ema ** 0.5, vol_floor)
        else:
            # Update the EMA volume
            self.vol_ema = alpha * self.vol_ema + self.alpha1 * volume
            # Update the EMA price
            self.price_emaw = alpha * self.price_emaw + self.alpha1 * volume * price_current
            self.price_ema = self.price_emaw / self.vol_ema
            # Update the EMM variance (volatility)
            diff_squared = price_deviation * price_deviation
            self.var_emaw = alpha * self.var_emaw + self.alpha1 * volume * diff_squared
            # Set the variance to be at least as large as the current squared deviation
            self.var_emaw = max(self.vol_ema * diff_squared, self.var_emaw)
            # Enforce the minimum volatility floor
            var_ema = self.var_emaw / self.vol_ema
            self.volat_ema = max(var_ema ** 0.5, vol_floor)

        return self.zscore, self.price_ema, self.volat_ema

    # end of calc_zscore_price_weighted method


    """
    Calculate the Z-score from the EMA price and the price variance weighted by the trading volumes.
    Returns: (zscore, price_ema, price_vol)
    """
    def calc_zscore_price_diff(self, price_current, alpha, volume, vol_floor=0.5):

        if _is_na_price(price_current):
            if self.price_ema is None:
                return 0.0, None, vol_floor
            volat_ema = max(max(float(self.var_emaw), 0.0) ** 0.5, vol_floor)
            return 0.0, self.price_ema, volat_ema

        if self.price_ema is None:
            # Initialize on first call
            self.price_previous = price_current
            self.price_ema = price_current  # Start with current price times volume
            self.var_emaw = vol_floor * vol_floor  # Start with floor variance times volume
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            # First call returns zero z-score
            return 0.0, price_current, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = price_current - self.price_ema
            price_diff = price_current - self.price_previous
            self.price_previous = price_current

            # Guard against tiny negative drift from floating point / bad params
            safe_var = max(float(self.var_emaw), 0.0)
            volat_ema = safe_var ** 0.5
            volat_ema = max(volat_ema, vol_floor)
            # volat_ema = max(volat_ema, vol_floor, abs(price_diff))

            # Calculate the Z-score
            zscore = price_deviation / volat_ema

            # Update the EMA return variance
            self.var_emaw = self.alpha_squared * self.var_emaw + self.alpha2 * (price_diff * price_diff)

            # Update the EMA price
            self.price_ema = alpha * self.price_ema + self.alpha1 * price_current

            return zscore, self.price_ema, volat_ema

    # end of calc_zscore_price_diff method


    """
    Calculate the Z-score from the EMA price and the return variance weighted by the trading volumes.
    Returns: (zscore, price_ema, price_vol)
    """
    def calc_zscore_price_diff_weighted(self, price_current, alpha, volume, vol_floor=0.5):

        if _is_na_price(price_current):
            if self.price_ema is None:
                return 0.0, None, vol_floor
            volat_ema = max(max(float(self.var_emaw), 0.0) ** 0.5, vol_floor)
            return 0.0, self.price_ema, volat_ema

        if self.price_ema is None:
            # Initialize on first call
            self.price_previous = price_current
            self.price_diff_sign = 0
            self.price_ema = price_current  # Start with current price
            self.price_ema = volume * price_current  # Start with current price times volume
            self.var_emaw = vol_floor * vol_floor  # Start with floor variance
            self.cum_var = volume * vol_floor * vol_floor  # Start with floor variance times volume
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.vol_ema = volume  # Initialize the volume to avoid division by zero
            # First call returns zero z-score
            return 0.0, price_current, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = price_current - self.price_ema
            price_diff = price_current - self.price_previous
            self.price_previous = price_current

            # Guard against tiny negative drift from floating point / bad params
            safe_var = max(float(self.var_emaw), 0.0)
            volat_ema = safe_var ** 0.5
            volat_ema = max(volat_ema, vol_floor)
            # volat_ema = max(volat_ema, vol_floor, abs(price_diff))

            # Calculate the Z-score
            zscore = price_deviation / volat_ema

            # Use VWAP for near-1 alpha, otherwise keep EMA update.
            if alpha >= 0.999:
                # Update the EMA volume
                self.vol_ema = self.vol_ema + volume
                # Update the EMA price
                self.price_ema = self.price_ema + volume * price_current
                self.price_ema = self.price_ema / self.vol_ema
                # Update the EMA return variance
                self.cum_var = self.cum_var + volume * (price_diff * price_diff)
                self.var_emaw = self.cum_var / self.vol_ema
            else:
                # Update the EMA volume
                self.vol_ema = alpha * self.vol_ema + self.alpha1 * volume
                # Update the EMA price
                self.price_ema = alpha * self.price_ema + self.alpha1 * volume * price_current
                self.price_ema = self.price_ema / self.vol_ema
                # Update the EMA return variance
                self.cum_var = self.alpha_squared * self.cum_var + self.alpha2 * volume * (price_diff * price_diff)
                self.var_emaw = self.cum_var / self.vol_ema

            return zscore, self.price_ema, volat_ema

    # end of calc_zscore_price_diff_weighted method


    """
    Calculate the Z-score from the EMA price and the return EMM exponentially moving maximum, weighted by the trading volumes.
    Returns: (zscore, price_ema, price_vol)
    """
    def calc_zscore_price_diff_emm(self, price_current, alpha, volume, vol_floor=0.5):

        # Handle invalid NA price.
        if _is_na_price(price_current):
            if any(value is None for value in (self.zscore, self.price_ema, self.volat_ema)):
                # Has not been initialized, return default values.
                return 0.0, 0.0, vol_floor
            else:
                # Has been initialized, return previous EMA values.
                return self.zscore, self.price_ema, self.volat_ema

        # Initialize for the first valid price.
        if any(value is None for value in (self.price_previous, self.zscore, self.price_ema, self.volat_ema)):
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.price_previous = price_current
            self.price_ema = price_current  # Initialize EMA price with current price
            self.price_emaw = volume * price_current  # Initialize weighted EMA price with current price times volume
            self.volat_ema = vol_floor  # Initialize the volatility EMA
            self.var_emaw = volume * vol_floor * vol_floor
            self.vol_ema = volume  # Initialize the EMA volume
            # First call returns zero z-score
            self.zscore = 0.0
            return self.zscore, self.price_ema, self.volat_ema

        # Calculate the price deviation from the current EMA
        price_deviation = price_current - self.price_ema
        price_diff = price_current - self.price_previous
        self.price_previous = price_current

        # Update the EMA price and variance (volatility)
        # Use VWAP for near-1 alpha, otherwise keep EMA update.
        if alpha >= 0.999:
            # Update the EMA volume
            self.vol_ema = self.vol_ema + volume
            # Update the EMA price
            self.price_emaw = self.price_emaw + volume * price_current
            self.price_ema = self.price_emaw / self.vol_ema
            # Update the EMM variance (volatility)
            diff_squared = price_diff * price_diff
            self.var_emaw = self.var_emaw + volume * diff_squared
            # Set the variance to be at least as large as the current squared deviation
            self.var_emaw = max(self.vol_ema * diff_squared, self.var_emaw)
            # Enforce the minimum volatility floor
            var_ema = self.var_emaw / self.vol_ema
            self.volat_ema = max(var_ema ** 0.5, vol_floor)
        else:
            # Update the EMA volume
            self.vol_ema = alpha * self.vol_ema + self.alpha1 * volume
            # Update the EMA price
            self.price_emaw = alpha * self.price_emaw + self.alpha1 * volume * price_current
            self.price_ema = self.price_emaw / self.vol_ema
            # Update the EMM variance (volatility)
            diff_squared = price_diff * price_diff
            self.var_emaw = alpha * self.var_emaw + self.alpha1 * volume * diff_squared
            # Set the variance to be at least as large as the current squared deviation
            self.var_emaw = max(self.vol_ema * diff_squared, self.var_emaw)
            # Enforce the minimum volatility floor
            var_ema = self.var_emaw / self.vol_ema
            self.volat_ema = max(var_ema ** 0.5, vol_floor)

        return self.zscore, self.price_ema, self.volat_ema

    # end of calc_zscore_price_diff_emm method


    """
    Calculate the Z-score using an external EMA/open reference and return
    volatility weighted by volumes.
    Returns: (zscore, price_ema, volat_ema)
    """
    def calc_zscore_open(self, price_current, price_ema, alpha, volume, vol_floor=0.5):

        if _is_na_price(price_current):
            if self.var_emaw is None:
                return 0.0, price_ema, vol_floor
            volat_ema = max(max(float(self.var_emaw), 0.0) ** 0.5, vol_floor)
            return 0.0, self.price_ema, volat_ema

        if self.price_ema is None:
            # Initialize on first call
            self.price_previous = price_current
            self.price_ema = price_current  # Keep internal EMA state aligned with incoming prices
            self.price_ema = volume * price_current
            self.var_emaw = vol_floor * vol_floor
            self.cum_var = volume * vol_floor * vol_floor
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.vol_ema = volume
            return 0.0, self.price_ema, vol_floor

        else:
            price_diff = price_current - self.price_previous
            self.price_previous = price_current

            safe_var = max(float(self.var_emaw), 0.0)
            volat_ema = safe_var ** 0.5
            volat_ema = max(volat_ema, vol_floor)

            # Use the provided EMA/open reference in the z-score numerator.
            price_deviation = price_current - price_ema
            zscore = price_deviation / volat_ema

            # Keep return-volatility state update identical to the weighted method.
            if alpha >= 0.999:
                self.vol_ema = self.vol_ema + volume
                self.price_ema = self.price_ema + volume * price_current
                self.price_ema = self.price_ema / self.vol_ema
                self.cum_var = self.cum_var + volume * (price_diff * price_diff)
                self.var_emaw = self.cum_var / self.vol_ema
            else:
                self.vol_ema = alpha * self.vol_ema + self.alpha1 * volume
                self.price_ema = alpha * self.price_ema + self.alpha1 * volume * price_current
                self.price_ema = self.price_ema / self.vol_ema
                self.cum_var = self.alpha_squared * self.cum_var + self.alpha2 * volume * (price_diff * price_diff)
                self.var_emaw = self.cum_var / self.vol_ema

            return zscore, self.price_ema, volat_ema

    # end of calc_zscore_open method


    """
    Calculate the EMA Sharpe ratio from the EMA return and return volatility,
    weighted by trading volume.
    Returns: (sharpema, ret_ema, volat_ema)
    """
    def calc_sharpema(self, price_current, alpha, volume, vol_floor=0.5):

        # Handle invalid NA price.
        if _is_na_price(price_current):
            if any(value is None for value in (self.sharpema, self.ret_ema, self.volat_ema)):
                # Has not been initialized, return default values.
                return 0.0, 0.0, vol_floor
            else:
                # Has been initialized, return previous EMA values.
                return self.sharpema, self.ret_ema, self.volat_ema

        # Initialize for the first valid price.
        if any(value is None for value in (self.price_previous, self.ret_ema, self.volat_ema)):
            self.return_alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.price_previous = price_current
            self.vol_ema = volume
            self.ret_ema = 0.0
            self.ret_emaw = 0.0
            self.var_emaw = volume * vol_floor * vol_floor
            self.volat_ema = vol_floor
            self.sharpema = 0.0
            return self.sharpema, self.ret_ema, self.volat_ema

        # Calculate the price difference from the previous price.
        price_diff = price_current - self.price_previous
        self.price_previous = price_current

        # Update the EMA of volume, variance, and return using the new price difference and volume.
        self.vol_ema = alpha * self.vol_ema + self.return_alpha1 * volume
        self.ret_emaw = alpha * self.ret_emaw + self.return_alpha1 * volume * price_diff
        self.var_emaw = self.alpha_squared * self.var_emaw + self.alpha2 * volume * price_diff * price_diff
        # Divide the weighted EMA return by the EMA volume to get the EMA return.
        self.ret_ema = self.ret_emaw / self.vol_ema
        # Divide the weighted EMA variance by the EMA volume to get the EMA volatility.
        self.volat_ema = max((self.var_emaw / self.vol_ema) ** 0.5, vol_floor)

        # Calculate the EMA Sharpe as the ratio of the EMA return divided by the EMA volatility.
        self.sharpema = self.ret_ema / self.volat_ema

        return self.sharpema, self.ret_ema, self.volat_ema

    # end of calc_sharpema method


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
    print("Testing calc_ema_price:")
    print("Price\tEMA")
    print("-" * 15)
    for price in prices:
        ema = EMAC.calc_ema_price(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")

    print("\nTesting calc_zscore_price:")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price in prices:
        zscore, ema, vol = EMAC.calc_zscore_price(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")
    """

    print("\nTesting calc_zscore_price_weighted:")
    print("Calculate the Z-score from the EMA price and the price variance weighted by the trading volumes.")
    print("Price\tEMA\tVol\tZ-Score")
    print("-" * 35)
    for price, volume in zip(prices, volumes):
        zscore, ema, vol = EMAC.calc_zscore_price_weighted(price, alpha, volume)
        print(f"{price:.1f}\t{ema:.2f}\t{vol:.3f}\t{zscore:.2f}")
    print("")

    EMAC.reset()
    print("Testing calc_ret_ema:")
    print("Price\tEMA Return")
    print("-" * 20)
    for price in prices[:5]:
        ret_ema = EMAC.calc_ret_ema(price, alpha)
        print(f"{price:.1f}\t{ret_ema:.2f}")
    print("")

    EMAC.reset()
    print("Testing calc_zscore_return:")
    print("Price\tEMA Return\tVol\tZ-Score")
    print("-" * 40)
    for price in prices[:5]:
        zscore, ret_ema, volat_ema = EMAC.calc_zscore_return(price, alpha)
        print(f"{price:.1f}\t{ret_ema:.2f}\t\t{volat_ema:.3f}\t{zscore:.2f}")
    print("")


