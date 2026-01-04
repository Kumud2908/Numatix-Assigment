
#Backtest Implementation

import pandas as pd
import sys
from backtesting import Backtest, Strategy as BTStrategy
from strategy import PullbackStrategy, Candle, Signal


class PullbackBacktestAdapter(BTStrategy):
    """
    Adapter between our strategy and backtesting.py library
    
    Key Implementation Details:
    1. HTF Delay: HTF candle becomes available 1 LTF candle AFTER completion
    2. Same aggregation logic as live trader
    3. Same signal generation timing
    """

    def init(self):
        """Initialize strategy and buffers"""
        self.strategy = PullbackStrategy()

        # Candle storage
        self.ltf_candles = []           # All closed LTF candles
        self.htf_candles = []           # All closed HTF candles
        self._htf_bucket = []           # Current HTF being built (5 LTF candles)
        
        # HTF Delay Implementation
        self._htf_pending = None        # HTF that just completed (not yet available)
        self._htf_available_next = False  # Flag: make pending available next tick

        # Position tracking
        self.current_trade = None
        self.trades_log = []
        
        # Metrics
        self.candle_count = 0
        self.htf_count = 0
        
        
        print("Backtest Initialized")
       

    def next(self):
        """
        Called every time a new LTF candle closes
        
        Execution Flow:
        1. Make pending HTF available (if any)
        2. Store new LTF candle
        3. Try to build HTF from 5 LTF candles
        4. Generate signal
        5. Execute order
        """
        self.candle_count += 1
        timestamp = self.data.index[-1]
        
        # make pending hft available
        # If HTF completed on previous candle, make it available now
        if self._htf_available_next and self._htf_pending is not None:
            self.htf_candles.append(self._htf_pending)
            self.htf_count += 1    
            
            self._htf_pending = None
            self._htf_available_next = False
        
        # store new hft candle
        ltf_candle = Candle(
            open=self.data.Open[-1],
            close=self.data.Close[-1]
        )
        self.ltf_candles.append(ltf_candle)
        
        # aggregate into htf
        self._htf_bucket.append(ltf_candle)
        
        if len(self._htf_bucket) == 5:
            # collected ltf make an htf
            htf_candle = Candle(
                open=self._htf_bucket[0].open,
                close=self._htf_bucket[-1].close
            )
            
            # Store as pending (will be available next candle)
            self._htf_pending = htf_candle
            self._htf_available_next = True
            self._htf_bucket.clear()

        
        if len(self.ltf_candles) < 2 or len(self.htf_candles) < 1:
            return  # Not enough data yet

        #  generate signal
        signal = self.strategy.generate_signal(
            self.ltf_candles,
            self.htf_candles,
            position_open=(self.current_trade is not None)
        )
        
        price = self.data.Close[-1]

        # Execute orders
        
        if signal == Signal.BUY:
            if self.current_trade is not None:
                return  # Already in position
            
            # Open position
            self.buy(size=0.1)
            
            self.current_trade = {
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "entry_time": timestamp,
                "entry_price": price,
                "entry_candle": self.candle_count,
                "entry_htf": self.htf_count
            }          
        elif signal == Signal.SELL:
            if self.current_trade is None:
                return  # No position to close
            
            # Close position
            self.sell()
            
            self.current_trade.update({
                "exit_time": timestamp,
                "exit_price": price,
                "exit_candle": self.candle_count,
                "exit_htf": self.htf_count
            })                     
            # Log completed trade
            self.trades_log.append(self.current_trade)
            self.current_trade = None


if __name__ == "__main__":
    
    print("\n Pullback stragegy backtest \n")  
    
    # loading data
    try:
        data = pd.read_csv("live_candles.csv")
       
    except FileNotFoundError:
        print("\nlive_candles.csv not found")
       
        sys.exit(1)
    
    # data preparation
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data.set_index("timestamp", inplace=True)
    data = data[~data.index.duplicated(keep="first")]
    
    print(f"Period: {data.index[0]} to {data.index[-1]}")
    
    # Check alignment
    first_minute = data.index[0].minute
    if first_minute % 5 != 0:
        print(f"\n WARNING: Data not aligned (starts at minute {first_minute})")
        print(f"   Live trader should have aligned this automatically")
        print(f"   Proceeding anyway, but results may not match live")
    else:
        print(f"Data properly aligned (starts at minute {first_minute})")
    
    # Convert to backtesting.py format
    data["Open"] = data["open"]
    data["High"] = data["open"]
    data["Low"] = data["open"]
    data["Close"] = data["close"]
    data["Volume"] = 1
    data = data[["Open", "High", "Low", "Close", "Volume"]]
    #running backtests
    
    bt = Backtest(
        data,
        PullbackBacktestAdapter,
        cash=100_000_000,
        commission=0.0,
        exclusive_orders=True
    )

    stats = bt.run()
    
    print(f"\nTrades executed: {len(stats._strategy.trades_log)}")
    
    if len(stats._strategy.trades_log) > 0:
        trades_df = pd.DataFrame(stats._strategy.trades_log)
        trades_df.to_csv("backtest_trades.csv", index=False)
        print(f"\nSaved {len(trades_df)} trades to backtest_trades.csv")
    
        print("TRADE DETAILS")
         
        for i, trade in enumerate(trades_df.itertuples(), 1):
            pnl = trade.exit_price - trade.entry_price
            pnl_pct = (pnl / trade.entry_price) * 100
            
            print(f"\nTrade #{i}:")
            print(f"  Entry:  {trade.entry_time} @ ${trade.entry_price:.2f} "
                  f"(candle {trade.entry_candle}, HTF {trade.entry_htf})")
            print(f"  Exit:   {trade.exit_time} @ ${trade.exit_price:.2f} "
                  f"(candle {trade.exit_candle}, HTF {trade.exit_htf})")
            print(f"  P&L:    ${pnl:.2f} ({pnl_pct:+.2f}%)")
    else:
        print("\n No trades executed")
    
   