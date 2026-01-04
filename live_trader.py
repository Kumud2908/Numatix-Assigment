"""
Live Trading System for Binance Testnet
"""
import os
import time
import csv
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from strategy import PullbackStrategy, Candle, Signal
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "Missing BINANCE_API_KEY or BINANCE_API_SECRET environment variables"
    )

class LiveTrader:

    def __init__(self, api_key: str, api_secret: str, symbol: str = "BTCUSDT"):
        """Initialize live trading system"""
        self.client = Client(api_key, api_secret, testnet=True)
        self.symbol = symbol
        
        # Strategy (SAME class as backtest)
        self.strategy = PullbackStrategy()
        
        # Candle storage
        self.ltf_candles = []           # All closed LTF candles
        self.htf_candles = []           # All closed HTF candles
        self._htf_bucket = []           # Current HTF being built
        
        # HTF Delay Implementation (CRITICAL FOR PARITY)
        self._htf_pending = None        # HTF that just completed
        self._htf_available_next = False  # Make available next tick
        
        # Alignment tracking
        self._alignment_complete = False
        
        # Execution state
        self.last_candle_ts = None
        self.current_trade = None
        
        # Metrics
        self.candle_count = 0
        self.htf_count = 0
        
        #  CSV LOGGING 
        # Trade log
        self.trade_file = open("live_trades.csv", "w", newline="")
        self.trade_writer = csv.DictWriter(
            self.trade_file,
            fieldnames=[
                "symbol", "direction",
                "entry_time", "entry_price", "entry_candle", "entry_htf",
                "exit_time", "exit_price", "exit_candle", "exit_htf"
            ]
        )
        self.trade_writer.writeheader()
        
        # Candle log (for backtest replay)
        self.candle_file = open("live_candles.csv", "w", newline="")
        self.candle_writer = csv.DictWriter(
            self.candle_file,
            fieldnames=["timestamp", "open", "close"]
        )
        self.candle_writer.writeheader()

    def fetch_latest_closed_candle(self) -> tuple[Candle, datetime]:
        """
        Fetch most recent CLOSED 1-minute candle from Binance
        
        Returns:
            (Candle, timestamp)
        """
        try:
            # Get last 2 candles
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=Client.KLINE_INTERVAL_1MINUTE,
                limit=2
            )
            
            # Use second-to-last (the closed one)
            k = klines[-2]
            
            candle = Candle(
                open=float(k[1]),
                close=float(k[4])
            )
            
            timestamp = datetime.fromtimestamp(k[0] / 1000)
            
            return candle, timestamp
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch candle: {e}")
            raise

    def get_btc_balance(self) -> float:
        """Get available BTC balance"""
        try:
            balances = self.client.get_account()["balances"]
            for b in balances:
                if b["asset"] == "BTC":
                    return float(b["free"])
            return 0.0
        except Exception as e:
            print(f"[ERROR] Failed to get balance: {e}")
            return 0.0
    
    def place_market_buy(self, quote_amount: float = 100.0):
        """Place market buy order (spend USDT to buy BTC)"""
        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=quote_amount
            )
            print(f"[ORDER] BUY executed: Order ID {order['orderId']}")
            return order
        except BinanceAPIException as e:
            print(f"[ERROR] Buy order failed: {e}")
            raise
    
    def place_market_sell(self):
        """Place market sell order (sell all BTC for USDT)"""
        try:
            qty = self.get_btc_balance()
            if qty <= 0:
                print("[WARNING] No BTC balance to sell")
                return None
            
            # Round to valid precision
            qty = round(qty, 6)
            
            order = self.client.create_order(
                symbol=self.symbol,
                side="SELL",
                type="MARKET",
                quantity=qty
            )
            print(f"[ORDER]  SELL executed: Order ID {order['orderId']}")
            return order
        except BinanceAPIException as e:
            print(f"[ERROR] Sell order failed: {e}")
            raise

    def run(self):
        """
        Main trading loop
        
        Flow:
        1. Wait for 5-minute alignment
        2. Make pending HTF available (if any)
        3. Fetch and store new LTF candle
        4. Aggregate into HTF
        5. Generate signal
        6. Execute order
        7. Log everything
        8. Sleep and repeat
        """        
        print(" LIVE TRADER STARTED")        
        print(f"Symbol: {self.symbol}")
        print(f"LTF: 1 minute")
        print(f"HTF: 5 minutes (delayed by 1 LTF candle)")
        print(f"Mode: Binance Testnet")
       
        
        while True:
            try:
                #  get new ltf candle 
                candle_ltf, ts = self.fetch_latest_closed_candle()
                
                # Skip if same candle (already processed)
                if ts == self.last_candle_ts:
                    time.sleep(30)
                    continue
                
                self.last_candle_ts = ts
                
                #  alignment phase
                if not self._alignment_complete:
                    current_minute = ts.minute
                    
                    if current_minute % 5 == 0:
                        # Perfect! We're on a 5-minute boundary
                        self._alignment_complete = True
                        print(f"[ALIGNMENT] Aligned at {ts}")
                        print(f"[ALIGNMENT] Starting strategy execution\n")
                    else:
                        # Not aligned yet, skip this candle
                        print(f"[ALIGNMENT] Waiting... (minute {current_minute}, "
                              f"need multiple of 5)")
                        time.sleep(30)
                        continue
                
                #  if not aligned process candles
                
                #  Making pending HTF available
                if self._htf_available_next and self._htf_pending is not None:
                    self.htf_candles.append(self._htf_pending)
                    self.htf_count += 1
                    
                    print(f"[HTF #{self.htf_count}] "
                          f"{self._htf_pending.open:.2f}→{self._htf_pending.close:.2f} | "
                          f"{'GREEN' if self._htf_pending.is_green else 'RED'}")
                    
                    self._htf_pending = None
                    self._htf_available_next = False
                
                #  Count and store LTF candle
                self.candle_count += 1
                self.ltf_candles.append(candle_ltf)
                
                # Log to CSV (for backtest replay)
                self.candle_writer.writerow({
                    "timestamp": ts,
                    "open": candle_ltf.open,
                    "close": candle_ltf.close
                })
                self.candle_file.flush()
                
                print(f"\n[LTF #{self.candle_count}] {ts} | "
                      f"{candle_ltf.open:.2f}→{candle_ltf.close:.2f} | "
                      f"{'GREEN' if candle_ltf.is_green else 'RED'}")
                
                #  Aggregate into HTF
                self._htf_bucket.append(candle_ltf)
                
                if len(self._htf_bucket) == 5:
                    #  LTF candles collected -> HTF complete
                    htf_candle = Candle(
                        open=self._htf_bucket[0].open,
                        close=self._htf_bucket[-1].close
                    )
                    
                    # Store as pending (available next candle)
                    self._htf_pending = htf_candle
                    self._htf_available_next = True
                    self._htf_bucket.clear()
                    
                    print(f"[HTF COMPLETED] "
                          f"{htf_candle.open:.2f}→{htf_candle.close:.2f} | "
                          f"Available next candle")
                
                #  Check minimum data
                if len(self.ltf_candles) < 2 or len(self.htf_candles) < 1:
                    print(f"[WAITING] Need more data: "
                          f"LTF={len(self.ltf_candles)}/2, HTF={len(self.htf_candles)}/1")
                    time.sleep(30)
                    continue
                
                #  Generate signal
                signal = self.strategy.generate_signal(
                    self.ltf_candles,
                    self.htf_candles,
                    position_open=(self.current_trade is not None)
                )
                
                position_status = "OPEN" if self.current_trade else "FLAT"
                print(f"[SIGNAL] {signal.value} | Position: {position_status}")
                
                price = candle_ltf.close
                
                #  Execute orders                
                if signal == Signal.BUY and self.current_trade is None:
                    print(f"\n{'='*80}")
                    print(f"[ENTRY] Candle #{self.candle_count} @ {ts}")
                    print(f"        Price: ${price:.2f} | HTF: #{self.htf_count}")
                    print(f"{'='*80}\n")
                    
                    # Execute buy
                    self.place_market_buy(quote_amount=100.0)
                    
                    # Track trade
                    self.current_trade = {
                        "symbol": self.symbol,
                        "direction": "LONG",
                        "entry_time": ts,
                        "entry_price": price,
                        "entry_candle": self.candle_count,
                        "entry_htf": self.htf_count
                    }
                
                elif signal == Signal.SELL and self.current_trade is not None:
                    print(f"\n{'='*80}")
                    print(f"[EXIT] Candle #{self.candle_count} @ {ts}")
                    print(f"       Price: ${price:.2f} | HTF: #{self.htf_count}")
                    
                    # Execute sell
                    self.place_market_sell()
                    
                    # Complete trade record
                    self.current_trade.update({
                        "exit_time": ts,
                        "exit_price": price,
                        "exit_candle": self.candle_count,
                        "exit_htf": self.htf_count
                    })
                    
                    # Calculate P&L
                    pnl = price - self.current_trade["entry_price"]
                    pnl_pct = (pnl / self.current_trade["entry_price"]) * 100
                    
                    print(f"       Entry: ${self.current_trade['entry_price']:.2f}")
                    print(f"       P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)")
                    print(f"{'='*80}\n")
                    
                    # Log to CSV
                    self.trade_writer.writerow(self.current_trade)
                    self.trade_file.flush()
                    
                    # Reset
                    self.current_trade = None
                
                # Wait for next candle
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Stopping trader...")
                self.shutdown()
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()
                time.sleep(30)
    
    def shutdown(self):     
        
        print("Shutting down")        
        
        print(f"\nSession Statistics:")
        print(f"  Candles processed: {self.candle_count}")
        print(f"  HTF candles: {self.htf_count}")
        
        # Close open position if any
        if self.current_trade is not None:
            print(f"\n Closing open position...")
            try:
                self.place_market_sell()
                print("Position closed")
            except Exception as e:
                print(f" Failed to close: {e}")
        
        # Close files
        self.trade_file.close()
        self.candle_file.close()
        
        

if __name__ == "__main__":  
        
    # Create and run trader
    trader = LiveTrader(API_KEY, API_SECRET, symbol="BTCUSDT")
    
    try:
        trader.run()
    except KeyboardInterrupt:
        trader.shutdown()