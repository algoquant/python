### Cancel all the open trade orders, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

# Cancel the open trade orders by running the script in the terminal:
#   python3 cancel_orders_all.py


from zoneinfo import ZoneInfo
import os
import sys
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader import create_daily_file_names


alpaca_sdk = AlpacAPI()
alpaca_sdk.create_trade_clients()


tzone = ZoneInfo("America/New_York")
dir_name = os.getenv("DATA_DIR_NAME") or "./"
file_names = create_daily_file_names("cancel_orders_all", dir_name, tzone)
canceled_file = file_names["canceled_file"]
state_file = file_names["state_file"]
submits_file = file_names["submits_file"]
fills_file = file_names["fills_file"]
error_file = file_names["error_file"]
alpaca_sdk.state_file = state_file
alpaca_sdk.submits_file = submits_file
alpaca_sdk.fills_file = fills_file
alpaca_sdk.canceled_file = canceled_file
alpaca_sdk.error_file = error_file

print(f"The state file is: {state_file}\n")
print(f"The submits file is: {submits_file}\n")
print(f"The fills file is: {fills_file}\n")
print(f"The canceled file is: {canceled_file}\n")
print(f"The error file is: {error_file}\n")

canceled_orders = alpaca_sdk.cancel_all_orders(canceled_file=canceled_file)
if canceled_orders:
    print(f"Finished cancelling orders and saved to {canceled_file}")

