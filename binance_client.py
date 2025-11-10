"""
Resilient Binance API Client with Rate Limiting and Error Handling
Implements robust connection management, retry logic, and monitoring
"""
import time
import random
from typing import Optional, Dict, Any, List
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from loguru import logger
import asyncio


class ResilientBinanceClient:
    """
    Production-grade Binance client with:
    - Exponential backoff retry logic
    - Rate limit monitoring and management
    - Timestamp synchronization
    - Comprehensive error handling
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Initialize Binance client with credentials

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet environment
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.max_retries = 5
        self.base_delay = 1
        self.symbol_info_cache = {}  # Cache for symbol precision info

        # Initialize client with retry logic
        self._initialize_client_with_retry()

        # Sync server time
        self._sync_server_time()

    def _initialize_client_with_retry(self):
        """Initialize Binance client with exponential backoff retry"""
        for attempt in range(self.max_retries):
            try:
                if self.testnet:
                    self.client = Client(self.api_key, self.api_secret, testnet=True)
                    logger.info("✅ Initialized Binance TESTNET client")
                else:
                    self.client = Client(self.api_key, self.api_secret)
                    logger.info("✅ Initialized Binance LIVE client")
                return  # Success
            except Exception as e:
                wait_time = self.base_delay * (2 ** attempt)
                if attempt < self.max_retries - 1:
                    logger.warning(f"Failed to initialize Binance client (attempt {attempt + 1}/{self.max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time + random.uniform(0, 1))
                else:
                    logger.error(f"Failed to initialize Binance client after {self.max_retries} attempts: {e}")
                    raise

    def _sync_server_time(self):
        """Synchronize with Binance server time"""
        try:
            server_time = self.client.get_server_time()
            logger.info(f"Synced with Binance server time: {server_time}")
        except Exception as e:
            logger.error(f"Failed to sync server time: {e}")

    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                return result

            except BinanceAPIException as e:
                # Handle timestamp errors
                if e.code == -1021:
                    logger.warning("Timestamp out of sync, resyncing...")
                    self._sync_server_time()
                    time.sleep(1)
                    continue

                # Handle rate limiting
                elif e.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', self.base_delay))
                    wait_time = min(retry_after, self.base_delay * (2 ** attempt))
                    logger.warning(f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time + random.uniform(0, 1))
                    continue

                # Handle insufficient balance
                elif e.code == -2010:
                    logger.error(f"Insufficient balance: {e.message}")
                    return None

                # Handle order-specific errors
                elif e.code in [-1013, -1111, -1112]:
                    logger.error(f"Order validation error: {e.message}")
                    return None

                else:
                    logger.error(f"Binance API error (code {e.code}): {e.message}")
                    if attempt == self.max_retries - 1:
                        raise e
                    time.sleep(self.base_delay * (2 ** attempt))

            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise e
                time.sleep(self.base_delay * (2 ** attempt))

        raise Exception(f"Failed after {self.max_retries} attempts")

    def get_account_balance(self) -> Dict[str, float]:
        """
        Get account balances for all assets

        Returns:
            Dict of asset balances
        """
        try:
            account = self.execute_with_retry(self.client.get_account)
            balances = {}
            for asset in account['balances']:
                free = float(asset['free'])
                locked = float(asset['locked'])
                total = free + locked
                if total > 0:
                    balances[asset['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }
            return balances
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return {}

    def get_usdt_balance(self) -> float:
        """
        Get current USDT balance from Binance

        Returns:
            Total USDT balance (free + locked)
        """
        try:
            balances = self.get_account_balance()
            if 'USDT' in balances:
                usdt_balance = balances['USDT']['total']
                logger.debug(f"Current USDT balance: ${usdt_balance:.2f}")
                return usdt_balance
            else:
                logger.warning("No USDT balance found in account")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting USDT balance: {e}")
            return 0.0

    def get_symbol_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Current price or None
        """
        try:
            ticker = self.execute_with_retry(self.client.get_symbol_ticker, symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def get_historical_klines(self, symbol: str, interval: str, limit: int = 500) -> List[List]:
        """
        Get historical kline/candlestick data

        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g., '5m', '1h')
            limit: Number of klines to retrieve

        Returns:
            List of kline data
        """
        try:
            klines = self.execute_with_retry(
                self.client.get_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            return []

    def get_symbol_precision(self, symbol: str) -> int:
        """
        Get the quantity precision for a trading pair

        Args:
            symbol: Trading pair symbol

        Returns:
            Number of decimal places allowed for quantity
        """
        if symbol in self.symbol_info_cache:
            return self.symbol_info_cache[symbol]

        try:
            info = self.client.get_symbol_info(symbol)
            if info:
                # Find the LOT_SIZE filter which defines quantity precision
                for filter in info['filters']:
                    if filter['filterType'] == 'LOT_SIZE':
                        step_size = filter['stepSize']
                        # Count decimal places in step size
                        precision = len(step_size.rstrip('0').split('.')[-1]) if '.' in step_size else 0
                        self.symbol_info_cache[symbol] = precision
                        logger.debug(f"Symbol {symbol} quantity precision: {precision}")
                        return precision

            # Default to 8 decimal places if not found
            logger.warning(f"Could not determine precision for {symbol}, using default 8")
            self.symbol_info_cache[symbol] = 8
            return 8
        except Exception as e:
            logger.error(f"Error getting symbol precision for {symbol}: {e}")
            # Default to 8 decimal places
            return 8

    def format_quantity(self, symbol: str, quantity: float) -> float:
        """
        Format quantity to correct precision for symbol

        Args:
            symbol: Trading pair symbol
            quantity: Raw quantity

        Returns:
            Properly formatted quantity
        """
        precision = self.get_symbol_precision(symbol)
        formatted = round(quantity, precision)
        logger.debug(f"Formatted quantity for {symbol}: {quantity} -> {formatted} ({precision} decimals)")
        return formatted

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[Dict]:
        """
        Place a market order

        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity

        Returns:
            Order response or None
        """
        try:
            # Format quantity to correct precision
            formatted_quantity = self.format_quantity(symbol, quantity)

            logger.info(f"Placing {side} market order: {formatted_quantity} {symbol}")
            order = self.execute_with_retry(
                self.client.order_market,
                symbol=symbol,
                side=side,
                quantity=formatted_quantity
            )
            logger.success(f"Market order placed: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Optional[Dict]:
        """
        Place a limit order

        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Order price

        Returns:
            Order response or None
        """
        try:
            # Format quantity to correct precision
            formatted_quantity = self.format_quantity(symbol, quantity)

            logger.info(f"Placing {side} limit order: {formatted_quantity} {symbol} @ {price}")
            order = self.execute_with_retry(
                self.client.order_limit,
                symbol=symbol,
                side=side,
                quantity=formatted_quantity,
                price=str(price)
            )
            logger.success(f"Limit order placed: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Optional[Dict]:
        """
        Place a stop loss order

        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            stop_price: Stop trigger price

        Returns:
            Order response or None
        """
        try:
            logger.info(f"Placing {side} stop loss: {quantity} {symbol} @ stop {stop_price}")
            order = self.execute_with_retry(
                self.client.create_order,
                symbol=symbol,
                side=side,
                type='STOP_LOSS_LIMIT',
                quantity=quantity,
                stopPrice=str(stop_price),
                price=str(stop_price * 0.99 if side == 'SELL' else stop_price * 1.01),
                timeInForce='GTC'
            )
            logger.success(f"Stop loss order placed: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
            return None

    def place_oco_order(self, symbol: str, side: str, quantity: float,
                       price: float, stop_price: float, stop_limit_price: float) -> Optional[Dict]:
        """
        Place OCO (One-Cancels-Other) order for take profit and stop loss

        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Take profit price
            stop_price: Stop loss trigger price
            stop_limit_price: Stop loss limit price

        Returns:
            Order response or None
        """
        try:
            logger.info(f"Placing OCO order: {symbol} TP:{price} SL:{stop_price}")
            order = self.execute_with_retry(
                self.client.create_oco_order,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=str(price),
                stopPrice=str(stop_price),
                stopLimitPrice=str(stop_limit_price),
                stopLimitTimeInForce='GTC'
            )
            logger.success(f"OCO order placed: {order['orderListId']}")
            return order
        except Exception as e:
            logger.error(f"Error placing OCO order: {e}")
            return None

    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Cancel an existing order

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.execute_with_retry(
                self.client.cancel_order,
                symbol=symbol,
                orderId=order_id
            )
            logger.info(f"Order {order_id} cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all open orders

        Args:
            symbol: Optional symbol to filter orders

        Returns:
            List of open orders
        """
        try:
            if symbol:
                orders = self.execute_with_retry(self.client.get_open_orders, symbol=symbol)
            else:
                orders = self.execute_with_retry(self.client.get_open_orders)
            return orders
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    def get_order_status(self, symbol: str, order_id: int) -> Optional[Dict]:
        """
        Get status of a specific order

        Args:
            symbol: Trading pair symbol
            order_id: Order ID

        Returns:
            Order status or None
        """
        try:
            order = self.execute_with_retry(
                self.client.get_order,
                symbol=symbol,
                orderId=order_id
            )
            return order
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading rules and symbol information

        Args:
            symbol: Trading pair symbol

        Returns:
            Symbol info or None
        """
        try:
            exchange_info = self.execute_with_retry(self.client.get_symbol_info, symbol)
            return exchange_info
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def get_min_notional(self, symbol: str) -> float:
        """
        Get minimum notional value for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Minimum notional value
        """
        try:
            info = self.get_symbol_info(symbol)
            if info:
                for filter_item in info['filters']:
                    if filter_item['filterType'] == 'MIN_NOTIONAL':
                        return float(filter_item['minNotional'])
            return 10.0  # Default minimum
        except Exception as e:
            logger.error(f"Error getting min notional: {e}")
            return 10.0


if __name__ == "__main__":
    """Test client functionality"""
    from config import Config

    # Test with paper trading credentials
    client = ResilientBinanceClient(
        Config.BINANCE_API_KEY,
        Config.BINANCE_API_SECRET,
        testnet=True
    )

    # Test basic functionality
    print("\nTesting Binance Client:")
    print("-" * 50)

    # Get BTC price
    btc_price = client.get_symbol_price('BTCUSDT')
    print(f"BTC Price: ${btc_price:,.2f}" if btc_price else "Failed to get price")

    # Get account balance
    balances = client.get_account_balance()
    print(f"\nAccount Balances: {len(balances)} assets with balance")
    for asset, balance in list(balances.items())[:5]:
        print(f"  {asset}: {balance['total']:.8f}")
