# Calculate the Exponential Moving Average with persistent state using function attributes

"""
Calculate the Exponential Moving Average EMA with persistent state.

Args:
    current_price (float): The latest price value
    alpha (float): Smoothing factor (0 < alpha <= 1)
    reset (bool): If True, resets the EMA state

Returns:
    float: Updated EMA value

Formula: EMA = α × previous_EMA + (1-α) × current_price

"""


def calc_ema(current_price, alpha, reset=False):

    # Persistent state variables
    if not hasattr(calc_ema, 'ema_price'):
        calc_ema.ema_price = None
    
    # Reset state if requested
    if reset:
        calc_ema.ema_price = None
        return None
    
    # Initialize EMA with first price if not set
    if calc_ema.ema_price is None:
        calc_ema.ema_price = float(current_price)
        return calc_ema.ema_price

    # Calculate new EMA: α × previous_EMA + (1-α) × current_price
    calc_ema.ema_price = alpha * calc_ema.ema_price + (1 - alpha) * current_price

    return calc_ema.ema_price


# Example usage:
if __name__ == "__main__":
    # Test the persistent EMA function
    alpha = 0.9  # 90% smoothing factor

    # Sample price data
    prices = [100.0, 102.0, 98.0, 105.0, 103.0, 99.0, 101.0]
    
    print("Price\tEMA")
    print("-" * 15)
    
    for price in prices:
        ema = calc_ema(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")
    
    print("\nResetting EMA state...")
    calc_ema(0, alpha, reset=True)
    
    print("\nStarting fresh:")
    print("Price\tEMA")
    print("-" * 15)
    
    for price in prices[:3]:
        ema = calc_ema(price, alpha)
        print(f"{price:.1f}\t{ema:.2f}")

