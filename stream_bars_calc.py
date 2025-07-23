# Needs more work, but this is a start

# Calculate the stock price bars from streaming trade prices
# https://forum.alpaca.markets/t/clarificaton-about-streaming-trade-data/14341/5

symbol = 'NVDA'
start = pd.to_datetime('2024-06-03 10:30:00').tz_localize('America/New_York')
end = pd.to_datetime('2024-06-03 11:00:00').tz_localize('America/New_York')

bars = (client.get_stock_bars(StockBarsRequest(
                                  symbol_or_symbols = symbol,
                                  timeframe = TimeFrame.Minute,
                                  start = start,
                                  end = end))
                                  .df
                                  .tz_convert('America/New_York', level='timestamp')
                                  .reset_index('symbol'))

trades = (client.get_stock_trades(StockTradesRequest(
                                  symbol_or_symbols = symbol,
                                  start = start,
                                  end = end))
                                  .df
                                  .tz_convert('America/New_York', level='timestamp')
                                  .reset_index('symbol'))

calculated_sizes = trades.resample('1T')['size'].sum()

bars['calculated_size'] = calculated_sizes
bars['calculated_diff'] = bars.calculated_size - bars.volume
