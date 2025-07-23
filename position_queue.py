# Example of an open position queue: keys are symbols, values are lists of trade prices (floats)

# Create empty position queue to store open positions
pos_queue = {}

def add_position(symbol, price):
    """Add a new position price for a symbol."""
    if symbol not in pos_queue:
        pos_queue[symbol] = []
    pos_queue[symbol].append(price)

def remove_position(symbol):
    """Remove (pop) the oldest position price for a symbol (FIFO)."""
    if symbol in pos_queue and pos_queue[symbol]:
        return pos_queue[symbol].pop(0)
    return None

def get_positions(symbol):
    """Get all position prices for a symbol."""
    return pos_queue.get(symbol, [])

# Example usage:
add_position("SPY", 500.25)
add_position("SPY", 501.10)
add_position("AAPL", 200.75)
add_position("AAPL", 201.25)

print("SPY position prices:", get_positions("SPY"))
print("AAPL position prices:", get_positions("AAPL"))

# Remove oldest SPY position price (FIFO)
removed = remove_position("SPY")
print("Removed SPY position price:", removed)
print("SPY position prices after removal:", get_positions("SPY"))

