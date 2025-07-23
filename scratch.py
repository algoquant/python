# Scratchpad code file for testing trading strategies with Alpaca API


    if (zscore > (1) & (num_available >= num_shares)): # If the price is significantly above the EMA price
        # Submit a sell order
        side = OrderSide.SELL
        order = "sell"
        # Limit price is equal to the last price plus a small adjustment
        limit_price = round(closep + deltap, 2)
        order_data = submit_trade(trading_client, symbol, num_shares, side, type, limit_price)
    elif (zscore < (-1) & (num_available >= num_shares)): # If the price is significantly below the EMA price
        # Submit a buy order
        side = OrderSide.BUY
        order = "buy"
        # Limit price is equal to the last price minus a small adjustment
        limit_price = round(closep - deltap, 2)
        order_data = submit_trade(trading_client, symbol, num_shares, side, type, limit_price)
    else:
        print(f"No trade executed for {symbol} at {closep} - no significant price change from EMA price {emap}")
        order = "none"


# Code for calculating the current position by listening to fill confirmations via the WebSocket
    # Confirm the order execution
    if order_data is not None:
        # Check the order status after waiting for 1 second
        print("Waiting 1 second for the order to be processed...")
        time.sleep(1)
        order_id = order_data.id
        order_status = trading_client.get_order_by_id(order_id)
        print(f"Order status: {order_status.status}")
        # If the order was successful, calculate the PnL
        if order == "buy":
            # If we bought, PnL is current price - buy price
            pnl = closep - order_data["limit_price"].values[0]
        else:
            # If we sold, PnL is sell price - current price
            pnl = order_data["limit_price"].values[0] - closep
        print(f"Trade executed: {order}, PnL: {pnl}")
    else:
        print(f"Trade not executed for {symbol} at {closep} - no significant price change from EMA price {emap}")


    if order_data is not None:
        # If the order was successful, calculate the PnL
        if order == "buy":
            # If we bought, PnL is current price - buy price
            pnl = closep - order_data["limit_price"].values[0]
        else:
            # If we sold, PnL is sell price - current price
            pnl = order_data["limit_price"].values[0] - closep
        print(f"Trade executed: {order}, PnL: {pnl}")


    # Calculate the new position and the realized PnL and unrealized PnL
    if position is not None:
        # If there is an open position, update the position variable
        position = position.qty
        # Calculate the unrealized PnL based on the current price and the average entry price
        pnl_unreal = (closep - position.avg_entry_price) * position.qty
        print(f"Unrealized PnL for {symbol}: {pnl_unreal}")
    else:
        # If there is no open position, set the position to 0
        position = 0
        pnl_unreal = 0

