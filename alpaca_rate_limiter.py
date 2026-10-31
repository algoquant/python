"""
WebSocket Connection Rate Limiter for Alpaca Trading API

This module provides utilities to handle Alpaca's rate limiting (HTTP 429 errors)
for WebSocket                  as            async def _connect():
            \"\"\"Internal connection function.\"\"\"
            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)
            
            # Start the stream with timeout
            await asyncio.wait_for(
                stream_client._run_forever(), 
                timeout=self.connection_timeout
            )f _connect():
            \"\"\"Internal connection function.\"\"\"
            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)f _connect():
            \"\"\"Internal connection function.\"\"\"
            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)
            
            # Start the stream with timeout
            await asyncio.wait_for(
                stream_client._run_forever(), 
                timeout=self.connection_timeout
            )_connect():
            \"\"\"Internal connection function.\"\"\"
            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)
            
            # Start the stream with timeoutc def _connect():
            \"\"\"Internal connection function.\"\"\"
            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)ctions and API requests.
"""

import asyncio
import time
import logging
from typing import Optional, Callable, Any


class AlpacaRateLimiter:
    """
    Rate limiter for Alpaca API connections with exponential backoff.
    
    Handles HTTP 429 errors and implements retry logic with exponential backoff
    to avoid overwhelming Alpaca's rate limits.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 5.0, max_delay: float = 300.0):
        """
        Initialize the rate limiter.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds to cap exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if the error is related to rate limiting."""
        error_str = str(error).lower()
        return any(indicator in error_str for indicator in [
            "429", "rate limit", "too many requests", 
            "server rejected websocket", "connection rejected"
        ])
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay using exponential backoff with jitter."""
        # Exponential backoff: base_delay * 2^(attempt-1)
        delay = self.base_delay * (2 ** (attempt - 1))
        
        # Add jitter (±20% randomization) to avoid thundering herd
        import random
        jitter = delay * 0.2 * (random.random() - 0.5)
        delay += jitter
        
        # Cap at max_delay
        return min(delay, self.max_delay)
    
    async def _enforce_rate_limit(self):
        """Enforce minimum time between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic for rate limiting.
        
        Args:
            func: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()
                
                # Execute the function
                self.logger.info(f"Executing function (attempt {attempt}/{self.max_retries})")
                
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                self.logger.info("Function executed successfully")
                return result
                
            except Exception as e:
                last_exception = e
                
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        self.logger.warning(
                            f"Rate limit error (attempt {attempt}/{self.max_retries}). "
                            f"Retrying in {delay:.1f} seconds..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                        raise RateLimitExceededError(
                            f"Rate limit exceeded after {self.max_retries} attempts"
                        ) from e
                else:
                    # Non-rate-limit error, re-raise immediately
                    self.logger.error(f"Non-rate-limit error: {e}")
                    raise e
        
        # If we get here, all retries were exhausted
        raise last_exception


class WebSocketConnectionManager:
    """
    Manages WebSocket connections with rate limiting and automatic reconnection.
    """
    
    def __init__(self, rate_limiter: Optional[AlpacaRateLimiter] = None):
        """
        Initialize the connection manager.
        
        Args:
            rate_limiter: Optional rate limiter instance. If None, creates a default one.
        """
        self.rate_limiter = rate_limiter or AlpacaRateLimiter()
        self.logger = logging.getLogger(__name__)
        self.connection_timeout = 30  # seconds
        
    async def connect_with_retry(self, stream_client, trade_update_handler=None):
        """
        Connect to stream with retry logic for rate limiting.
        
        Args:
            stream_client: Alpaca TradingStream client
            trade_update_handler: Optional callback handler function
            
        Returns:
            True if connection successful, False otherwise
        """
        async def _connect():
            """Internal connection function."""
            if trade_update_handler:
                            # Subscribe to updates if handler provided
            if trade_update_handler:
                stream_client.subscribe_trade_updates(trade_update_handler)
            
            # Start the stream with timeout
            await asyncio.wait_for(
                stream_client._run_forever(), 
                timeout=self.connection_timeout
            )
        
        try:
            await self.rate_limiter.execute_with_retry(_connect)
            return True
        except (RateLimitExceededError, asyncio.TimeoutError) as e:
            self.logger.error(f"Connection failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected connection error: {e}")
            return False
    
    async def cleanup_connection(self, stream_client):
        """Safely cleanup WebSocket connection."""
        try:
            await stream_client.stop_ws()
        except Exception as e:
            self.logger.debug(f"Error stopping WebSocket: {e}")
        
        try:
            await stream_client.close()
        except Exception as e:
            self.logger.debug(f"Error closing stream client: {e}")


class RateLimitExceededError(Exception):
    """Exception raised when rate limits are exceeded after all retries."""
    pass


# Convenience functions
async def execute_with_rate_limiting(func: Callable, *args, **kwargs) -> Any:
    """
    Convenience function to execute any function with rate limiting.
    
    Args:
        func: Function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function execution
    """
    rate_limiter = AlpacaRateLimiter()
    return await rate_limiter.execute_with_retry(func, *args, **kwargs)


def create_rate_limited_clients(alpaca_sdk, max_retries=3):
    """
    Create Alpaca clients with rate limiting.
    
    Args:
        alpaca_sdk: AlpacaSDK instance
        max_retries: Maximum retry attempts
        
    Returns:
        Tuple of (trading_client, confirm_stream, data_client)
    """
    rate_limiter = AlpacaRateLimiter(max_retries=max_retries)
    
    def _create_clients():
        trading_client, confirm_stream = alpaca_sdk.create_trade_clients()
        data_client = alpaca_sdk.create_data_client()
        return trading_client, confirm_stream, data_client
    
    # Use synchronous execution for client creation
    import time
    for attempt in range(max_retries):
        try:
            return _create_clients()
        except Exception as e:
            if rate_limiter._is_rate_limit_error(e):
                if attempt < max_retries - 1:
                    delay = rate_limiter._calculate_delay(attempt + 1)
                    print(f"⚠️  Rate limit encountered. Waiting {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise RateLimitExceededError("Max retries exceeded during client creation")
            else:
                raise e
    
    raise Exception("Failed to create clients after all retries")