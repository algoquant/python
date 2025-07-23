# Interactive open position queue: keys are symbols, values are lists of trade prices (floats)

# Create empty position queue to store open positions
pos_queue = {}

def add_position(symbol, price):
    if symbol not in pos_queue:
        pos_queue[symbol] = []
    pos_queue[symbol].append(price)

def remove_position(symbol):
    if symbol in pos_queue and pos_queue[symbol]:
        return pos_queue[symbol].pop(0)
    return None

def get_positions(symbol):
    return pos_queue.get(symbol, [])

def print_menu():
    print("\n--- Open Position Queue Menu ---")
    print("1. Add position")
    print("2. Remove oldest position")
    print("3. Show positions for symbol")
    print("4. Show all positions")
    print("5. Calculate market value of positions")
    print("6. Exit")

while True:
    print_menu()
    choice = input("Enter your choice (1-5): ").strip()
    if choice == "1":
        symbol = input("Enter symbol: ").strip().upper()
        try:
            price = float(input("Enter trade price: "))
            add_position(symbol, price)
            print(f"Added {symbol} at {price}")
        except ValueError:
            print("Invalid price.")
    elif choice == "2":
        symbol = input("Enter symbol: ").strip().upper()
        removed = remove_position(symbol)
        if removed is not None:
            print(f"Removed oldest {symbol} position at {removed}")
        else:
            print(f"No positions to remove for {symbol}")
    elif choice == "3":
        symbol = input("Enter symbol: ").strip().upper()
        print(f"{symbol} position prices: {get_positions(symbol)}")
    elif choice == "4":
        print("All positions:")
        for sym, prices in pos_queue.items():
            print(f"{sym}: {prices}")
    if choice == "5":
        symbol = input("Enter symbol: ").strip().upper()
        try:
            market_price = float(input("Enter trade price: "))
            mtm = sum((market_price - price) for price in pos_queue[symbol])
            print(f"Mark value = {mtm}")
        except ValueError:
            print("Invalid price.")
    elif choice == "6":
        print("Exiting.")
        break
    else:
        print("Invalid choice. Please enter 1-5.")

