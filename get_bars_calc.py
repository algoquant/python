# Shows how to request from Alpaca historical stock bars and trades,
# and how to aggregate the trades to compare with the bars.

# Calculate the stock price bars from streaming trade prices
# https://forum.alpaca.markets/t/clarificaton-about-streaming-trade-data/14341/5

symbol = 'NVDA'
startd = pd.to_datetime('2024-06-03 10:30:00').tz_localize('America/New_York')
endd = pd.to_datetime('2024-06-03 11:00:00').tz_localize('America/New_York')

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

bars = (data_client.get_stock_bars(StockBarsRequest(
                                  symbol_or_symbols = symbol,
                                  timeframe = TimeFrame.Minute,
                                  start = startd,
                                  end = endd))
                                  .df
                                  .tz_convert('America/New_York', level='timestamp')
                                  .reset_index('symbol'))

trades = (data_client.get_stock_trades(StockTradesRequest(
                                  symbol_or_symbols = symbol,
                                  start = startd,
                                  end = endd))
                                  .df
                                  .tz_convert('America/New_York', level='timestamp')
                                  .reset_index('symbol'))

calculated_sizes = trades.resample('1T')['size'].sum()

bars['calculated_sizes'] = calculated_sizes
bars['calculated_diff'] = bars.calculated_sizes - bars.volume
