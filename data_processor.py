from numpy import sqrt
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockLatestBarRequest
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
import os
import asyncio
import threading
from queue import Queue
import signal
import sys

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Global variables matching stream_ema.py
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_pretty = time_now.strftime("%Y-%m-%d")
date_short = time_now.strftime("%Y%m%d")

# EMA parameters
alpha_param = 0.99
bollinger_width = 1.0
spike_threshold = 2
min_size = 100
max_frame_size = 1000
num_ticks_plot = 100

# Global state variables
price_ema = None
price_var = None
price_frame = None
prev_price = None
prev_spike = False
num_ticks = 0
data_queue = Queue()
data_client = None  # Make data_client global to manage connections

# Initialize clients
hist_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

def create_data_client():
    """Create a new stream client with proper error handling"""
    global data_client
    
    # Force close any existing connection
    if data_client is not None:
        try:
            data_client.stop()
            time.sleep(1)  # Give time for cleanup
        except:
            pass
        data_client = None
    
    # Try SIP first, fallback to IEX if authentication fails
    try:
        data_feed = DataFeed.SIP
        data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=data_feed)
        print("Attempting SIP data feed (premium)")
        # Test connection by creating a simple request
        return data_feed
    except Exception as e:
        print(f"SIP data feed failed: {e}")
        try:
            print("Falling back to IEX data feed (free)")
            data_feed = DataFeed.IEX
            data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=data_feed)
            return data_feed
        except Exception as e2:
            print(f"IEX data feed also failed: {e2}")
            if "connection limit exceeded" in str(e2).lower():
                print("Connection limit exceeded. Please wait 10-15 minutes and try again.")
                print("Make sure no other instances of the app are running.")
            raise e2

class EMARealTimeProcessor:
    def __init__(self, symbol="SPY"):
        self.symbol = symbol.upper()
        self.running = False
        self.stream_thread = None
        self.data_feed = None
        self.initialize_ema()
        
    def initialize_ema(self):
        """Initialize EMA values with latest trade data - matching stream_ema.py"""
        global price_ema, price_var, prev_price, price_frame
        
        print(f"Initializing the EMA prices for {self.symbol}\n")
        
        # Check if API credentials are loaded
        if not DATA_KEY or not DATA_SECRET:
            print("ERROR: Alpaca API credentials not found!")
            print("Please check your /Users/jerzy/Develop/Python/.env file and ensure DATA_KEY and DATA_SECRET are set")
            return
        
        print(f"Using API Key: {DATA_KEY[:8]}...")
        
        # Create data feed for this instance
        self.data_feed = create_data_client()
        
        try:
            # Get the latest trade price and size
            request_params = StockLatestTradeRequest(symbol_or_symbols=self.symbol, feed=self.data_feed)
            latest_price = hist_client.get_stock_latest_trade(request_params)
            latest_price = latest_price[self.symbol]
            
            time_stamp = latest_price.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
            trade_price = latest_price.price
            trade_size = latest_price.size
            
            print(f"Latest trade price for {self.symbol}: Price = {trade_price}, Size = {trade_size}")
            
            # Get the latest 1-minute bar prices
            request_params = StockLatestBarRequest(symbol_or_symbols=self.symbol, feed=self.data_feed)
            bar_data = hist_client.get_stock_latest_bar(request_params)
            bar_data = bar_data[self.symbol].model_dump()
            
            print(f"Latest bar prices: Open: {bar_data['open']}, High: {bar_data['high']}, Low: {bar_data['low']}, Close: {bar_data['close']}, Volume: {bar_data['volume']}, VWAP: {bar_data['vwap']}\n")
            
            # Initialize EMA values exactly like stream_ema.py
            price_ema = trade_price
            price_var = ((bar_data["high"] - bar_data["low"])/5) ** 2
            price_vol = sqrt(price_var)
            prev_price = trade_price
            
            # Create initial DataFrame
            price_dict = {
                "timestamp": time_stamp,
                "symbol": self.symbol,
                "price": trade_price,
                "volume": trade_size,
                "ema_price": price_ema,
                "volatility": price_vol,
            }
            price_frame = pd.DataFrame([price_dict])
            
            print("The live and EMA prices:\n")
            
        except Exception as e:
            print(f"ERROR initializing EMA: {e}")
            print("This could be due to:")
            print("1. Invalid API credentials")
            print("2. API key doesn't have market data permissions")
            print("3. Network connectivity issues")
            print("4. Invalid symbol")
            print("5. Connection limit exceeded - try again in a few minutes")
            raise
    
    def calc_ema(self, trade_price, trade_size, time_stamp):
        """Calculate EMA - exact copy from stream_ema.py"""
        global price_ema, price_var, price_frame
        
        # Update EMA price
        price_ema = alpha_param * price_ema + (1 - alpha_param) * trade_price
        
        # Update price variance
        price_var = alpha_param * price_var + (1 - alpha_param) * (trade_price - price_ema) ** 2
        
        # Calculate volatility
        price_vol = sqrt(price_var)
        
        print(f"{time_stamp} {self.symbol} Price: {round(trade_price, ndigits=2)}, Size: {trade_size}, EMA price: {round(price_ema, ndigits=2)}, Volatility: {round(price_vol, ndigits=4)}")
        
        # Create price dictionary
        price_dict = {
            "timestamp": time_stamp,
            "symbol": self.symbol,
            "price": trade_price,
            "volume": trade_size,
            "ema_price": price_ema,
            "volatility": price_vol,
        }
        
        # Create single frame and append to price_frame
        single_frame = pd.DataFrame([price_dict])
        price_frame = pd.concat([price_frame, single_frame], ignore_index=True)
        
        # Keep only last max_frame_size records to limit memory usage
        if len(price_frame) > max_frame_size:
            price_frame = price_frame.tail(max_frame_size).reset_index(drop=True)
        
        return price_frame
    
    async def handle_prices(self, latest_price):
        """Handle price updates - exact copy from stream_ema.py"""
        global prev_spike, prev_price, price_var, num_ticks
        
        trade_size = latest_price.size
        
        # Check if the trade size is above the minimum size
        if trade_size >= min_size:
            symbol = latest_price.symbol
            time_stamp = latest_price.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
            trade_price = latest_price.price
            
            # Check if an isolated price spike was detected
            price_spike = abs(trade_price - prev_price) > spike_threshold * sqrt(price_var)
            if price_spike and not prev_spike:
                # A price spike was detected, print a message
                print(f"{time_stamp} {symbol} Price spike detected: {trade_price} (previous price: {prev_price})")
                # Set the flag to indicate that a price spike was detected
                prev_spike = True
            elif (not price_spike) or (price_spike and prev_spike):
                # The current price is not a spike or price has returned to pre-spike value
                prev_spike = False
                # Update the previous price for the next iteration
                prev_price = trade_price
                # Calculate the EMA price and the variance using the latest trade price
                price_frame = self.calc_ema(trade_price, trade_size, time_stamp)
                
                # Add Bollinger Bands for web display
                upper_band = price_ema + bollinger_width * sqrt(price_var)
                lower_band = price_ema - bollinger_width * sqrt(price_var)
                
                # Create data for web display
                web_data = {
                    'timestamp': time_stamp,
                    'symbol': symbol,
                    'price': round(trade_price, 2),
                    'volume': trade_size,
                    'ema_price': round(price_ema, 2),
                    'volatility': round(sqrt(price_var), 4),
                    'upper_band': round(upper_band, 2),
                    'lower_band': round(lower_band, 2)
                }
                
                # Put data in queue for web display
                data_queue.put(web_data)
                
                # Increment tick counter
                num_ticks += 1
    
    def start_stream(self):
        """Start the streaming in a separate thread"""
        if not self.running:
            self.running = True
            self.stream_thread = threading.Thread(target=self._run_stream)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            print(f"Started streaming for {self.symbol}")
            print("Press Ctrl-C to stop the stream...\n")
    
    def stop_stream(self):
        """Stop the streaming"""
        global data_client
        self.running = False
        if self.stream_thread:
            try:
                if data_client:
                    data_client.stop()
                    data_client = None
            except Exception as e:
                print(f"Error stopping stream: {e}")
            print(f"Stopped streaming for {self.symbol}")
    
    def _run_stream(self):
        """Run the stream in async context"""
        global data_client
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if data_client:
                # Subscribe to trades
                data_client.subscribe_trades(self.handle_prices, self.symbol)
                loop.run_until_complete(data_client.run())
        except Exception as e:
            time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
            error_text = f"{time_stamp} WebSocket error: {e}"
            print(error_text)
            if "connection limit exceeded" in str(e).lower():
                print("Connection limit exceeded. Please:")
                print("1. Wait a few minutes before trying again")
                print("2. Make sure no other instances are running")
                print("3. Check if you have multiple connections open")
            time.sleep(5)
        finally:
            loop.close()

# Global processor instance
processor = None

def initialize_processor(symbol="SPY"):
    """Initialize the EMA processor"""
    global processor
    # Clean up any existing processor
    if processor:
        processor.stop_stream()
    processor = EMARealTimeProcessor(symbol)
    processor.start_stream()

def get_latest_data():
    """Get the latest data from the queue"""
    if not data_queue.empty():
        return data_queue.get()
    return None

def process_data(data):
    """Process incoming data for the front end"""
    return data

def get_current_stats():
    """Get current EMA statistics"""
    if processor:
        return {
            'symbol': processor.symbol,
            'num_ticks': num_ticks,
            'alpha_param': alpha_param,
            'bollinger_width': bollinger_width,
            'spike_threshold': spike_threshold,
            'min_size': min_size
        }
    return None

def generate_random_data():
    """Fallback function for testing without real data"""
    return {
        'timestamp': datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S"),
        'symbol': 'TEST',
        'price': 100 + (time.time() % 10),
        'volume': 1000,
        'ema_price': 100 + (time.time() % 8),
        'volatility': 0.5,
        'upper_band': 105,
        'lower_band': 95
    }

def cleanup():
    """Clean up resources"""
    global processor, data_client
    if processor:
        processor.stop_stream()
        processor = None
    if data_client:
        try:
            data_client.stop()
        except:
            pass
        data_client = None

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    """Handle Ctrl-C (SIGINT) gracefully"""
    print("\n\nCtrl-C pressed! Exiting gracefully...")
    cleanup()
    sys.exit(0)

# Set up signal handler
signal.signal(signal.SIGINT, signal_handler)