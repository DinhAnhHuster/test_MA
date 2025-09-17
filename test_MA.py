#!/usr/bin/env python3
"""
Strategy for Poloniex BTC Trading
- Buys BTC if price crosses above 10-period Moving Average.
- Sells BTC if price crosses below 10-period Moving Average.
"""

## Paper Trade / Live Trade

import os
import sys
import time
import json
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')

# Add the parent directory to the path to import our modules
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.insert(0, PROJECT_ROOT)

from logger import logger_database, logger_error, logger_access
from constants import set_constants, get_constants
from exchange_api_spot.user import get_client_exchange
from utils import (
    get_line_number,
    update_key_and_insert_error_log,
    generate_random_string,
    get_precision_from_real_number,
    get_arg
)

class MovingAverageCrossoverStrategy:
    def __init__(self, api_key="", secret_key="", passphrase="", session_key=""):
        """
        Initialize the Moving Average Crossover strategy
        
        Args:
            api_key (str): Poloniex API key
            secret_key (str): Poloniex secret key
            passphrase (str): Poloniex passphrase
            session_key (str): Session key for tracking
        """
        self.symbol = "BTC"
        self.quote = "USDT"
        self.trade_amount = 0.0005  # Amount of BTC to buy/sell
        self.ma_period = 10  # 10-period Moving Average
        self.timeframe = '5m' # Timeframe for candles (e.g., '5m', '15m', '1h', '4h', '1d')
        
        self.run_key = generate_random_string()
        self.session_key = session_key
        
        # State management: 'none' (no position) or 'long' (holding BTC)
        self.position_status = 'none' 
        
        # Initialize Poloniex client
        try:
            account_info = {
                "api_key": api_key,
                "secret_key": secret_key,
                "passphrase": passphrase,
            }
            
            self.client = get_client_exchange(
                exchange_name="poloniex",
                acc_info=account_info,
                symbol=self.symbol,
                quote=self.quote,
                session_key=session_key,
            )

            logger_access.info(f"Poloniex client initialized for {self.symbol}/{self.quote}")
            logger_database.info(f"MA Crossover strategy initialized for {self.symbol}/{self.quote}")
        except Exception as e:
            logger_error.error(f"Failed to initialize Poloniex client: {e}")
            raise

    def get_current_price(self):
        """
        Get the current price of the symbol from Poloniex.
        
        Returns:
            float: Current price in USDT, or None if an error occurs.
        """
        try:
            price_data = self.client.get_price()
            if price_data and 'price' in price_data:
                current_price = float(price_data['price'])
                logger_access.info(f"Current {self.symbol} price: ${current_price:,.2f} {self.quote}")
                return current_price
            else:
                logger_error.error("Failed to get price data - invalid response")
                return None
        except Exception as e:
            logger_error.error(f"Error getting price: {e}")
            update_key_and_insert_error_log(
                self.run_key, self.symbol, get_line_number(), "POLONIEX",
                "strategy.py", f"Error getting price: {e}"
            )
            return None

    def calculate_moving_average(self):
        """
        Calculate the Moving Average for the specified period.

        Returns:
            float: The calculated MA value, or None if an error occurs.
        """
        try:
            # Fetch historical data (candlesticks)
            # The client needs a method like `get_klines`
            klines = self.client.get_klines(
                timeframe=self.timeframe, 
                limit=self.ma_period
            )
            
            if not klines or len(klines) < self.ma_period:
                logger_error.warning(f"Could not fetch enough data for MA calculation. Got {len(klines)} candles.")
                return None

            # Extract closing prices (assuming kline format is [timestamp, open, high, low, close, ...])
            closing_prices = [float(k[4]) for k in klines]
            
            # Calculate the average
            ma_value = sum(closing_prices) / len(closing_prices)
            logger_access.info(f"Calculated MA({self.ma_period}) on '{self.timeframe}' timeframe: ${ma_value:,.2f}")
            return ma_value
            
        except Exception as e:
            logger_error.error(f"Error calculating Moving Average: {e}")
            update_key_and_insert_error_log(
                self.run_key, self.symbol, get_line_number(), "POLONIEX",
                "strategy.py", f"Error calculating MA: {e}"
            )
            return None

    def place_buy_order(self):
        """
        Place a market buy order for the specified trade amount.
        
        Returns:
            bool: True if the order was placed successfully, False otherwise.
        """
        try:
            logger_access.info(f"🛒 Placing BUY order for {self.trade_amount} {self.symbol} at market price...")
            order_result = self.client.place_order(
                side_order='BUY',
                quantity=self.trade_amount,
                order_type='MARKET',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_id = order_result.get('data', {}).get('orderId', 'N/A')
                logger_access.info(f"✅ BUY order placed successfully! Order ID: {order_id}")
                logger_database.info(f"BUY order success - ID: {order_id}, Qty: {self.trade_amount} {self.symbol}")
                return True
            else:
                logger_error.error(f"Failed to place BUY order: {order_result}")
                return False
                
        except Exception as e:
            logger_error.error(f"Error placing BUY order: {e}")
            update_key_and_insert_error_log(
                self.run_key, self.symbol, get_line_number(), "POLONIEX",
                "strategy.py", f"Error placing buy order: {e}"
            )
            return False

    def place_sell_order(self):
        """
        Place a market sell order for the specified trade amount.
        
        Returns:
            bool: True if the order was placed successfully, False otherwise.
        """
        try:
            logger_access.info(f"📉 Placing SELL order for {self.trade_amount} {self.symbol} at market price...")
            order_result = self.client.place_order(
                side_order='SELL',
                quantity=self.trade_amount,
                order_type='MARKET',
                force='normal'
            )
            
            if order_result and order_result.get('code') == 0:
                order_id = order_result.get('data', {}).get('orderId', 'N/A')
                logger_access.info(f"✅ SELL order placed successfully! Order ID: {order_id}")
                logger_database.info(f"SELL order success - ID: {order_id}, Qty: {self.trade_amount} {self.symbol}")
                return True
            else:
                logger_error.error(f"Failed to place SELL order: {order_result}")
                return False
                
        except Exception as e:
            logger_error.error(f"Error placing SELL order: {e}")
            update_key_and_insert_error_log(
                self.run_key, self.symbol, get_line_number(), "POLONIEX",
                "strategy.py", f"Error placing sell order: {e}"
            )
            return False

    def run_strategy(self):
        """
        Main strategy logic based on MA crossover.
        """
        logger_access.info("-" * 50)
        logger_access.info(f"Executing MA Crossover Strategy | Current Position: {self.position_status.upper()}")
        
        try:
            # 1. Get current price and MA value
            current_price = self.get_current_price()
            moving_average = self.calculate_moving_average()
            
            if current_price is None or moving_average is None:
                logger_access.info("Cannot proceed without price and MA data. Skipping this iteration.")
                return False

            logger_database.info(f"Price: {current_price:.2f}, MA({self.ma_period}): {moving_average:.2f}, Position: {self.position_status}")

            # 2. Decision Logic
            # BUY condition: Price crosses above MA and we have no position
            if current_price > moving_average and self.position_status == 'none':
                logger_access.info(f"📈 BUY SIGNAL: Price (${current_price:,.2f}) > MA (${moving_average:,.2f})")
                
                success = self.place_buy_order()
                if success:
                    self.position_status = 'long' # Update state after successful buy
                    return True
                else:
                    logger_error.error("Buy order failed. State remains 'none'.")
                    return False

            # SELL condition: Price crosses below MA and we are in a long position
            elif current_price < moving_average and self.position_status == 'long':
                logger_access.info(f"📉 SELL SIGNAL: Price (${current_price:,.2f}) < MA (${moving_average:,.2f})")

                success = self.place_sell_order()
                if success:
                    self.position_status = 'none' # Update state after successful sell
                    return True
                else:
                    logger_error.error("Sell order failed. State remains 'long'.")
                    return False
            
            # HOLD condition: No signal or already in the desired state
            else:
                if self.position_status == 'long':
                    logger_access.info(f"HOLDING: Price (${current_price:,.2f}) is still above MA (${moving_average:,.2f}). No action.")
                else:
                    logger_access.info(f"WAITING: Price (${current_price:,.2f}) is still below MA (${moving_average:,.2f}). No action.")
                return True
                
        except Exception as e:
            logger_error.error(f"Strategy execution error: {e}")
            update_key_and_insert_error_log(
                self.run_key, self.symbol, get_line_number(), "POLONIEX",
                "strategy.py", f"Strategy error: {e}"
            )
            return False

def main():
    """
    Main function to run the strategy.
    """
    logger_access.info("Running MA Crossover Strategy...")
    logger_access.info("-" * 50)

    params = get_constants()
    SESSION_ID     = params.get("SESSION_ID", "")
    API_KEY        = params.get("API_KEY", "")
    SECRET_KEY     = params.get("SECRET_KEY", "")
    PASSPHRASE     = params.get("PASSPHRASE", "")
    
    if not all([API_KEY, SECRET_KEY, SESSION_ID]):
        print("API_KEY, SECRET_KEY, and SESSION_ID are required.")
        logger_error.critical("Missing required credentials or session ID.")
        return
    
    logger_access.info("Environment variables loaded successfully.")
    logger_database.info("MA Crossover Strategy starting...")

    try:
        # Initialize strategy
        strategy = MovingAverageCrossoverStrategy(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            passphrase=PASSPHRASE,
            session_key=SESSION_ID,
        )
        logger_access.info("Strategy initialized successfully.")

        # Strategy execution loop
        iteration = 0
        while True:
            iteration += 1
            logger_access.info(f"\n--- Strategy Iteration #{iteration} ---")
            logger_database.info(f"Running strategy iteration #{iteration}")
            
            strategy.run_strategy()
            
            # Sleep between iterations to avoid spamming API
            sleep_duration = 60 # Check every 60 seconds
            logger_access.info(f"⏸ Waiting {sleep_duration} seconds before next iteration...")
            time.sleep(sleep_duration)
        
    except KeyboardInterrupt:
        logger_access.info("\nStrategy stopped by user.")
        logger_database.info("MA Crossover Strategy stopped by user.")
    except Exception as e:
        logger_error.error(f"Fatal error in main loop: {e}")
        update_key_and_insert_error_log(
            generate_random_string(), "BTC", get_line_number(), "POLONIEX",
            "strategy.py", f"Fatal error: {e}"
        )

if __name__ == "__main__":
    main()