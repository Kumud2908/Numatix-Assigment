"""
Multi-Timeframe Pullback Strategy

Strategy Logic:
- HTF (Higher Timeframe): Confirms uptrend (green candle)
- LTF (Lower Timeframe): Detects pullback and continuation
- Entry: Previous LTF red + Current LTF green (in HTF uptrend)
- Exit: Current LTF turns red (momentum breaks)

This is a STATELESS strategy - it doesn't track positions internally.
The execution layer (backtest/live) handles state management.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List


class Signal(Enum):
    """Trading signals"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Candle:
    """
    Simple candle representation with open and close prices
    """
    open: float
    close: float
    
    @property
    def is_green(self) -> bool:
        """Bullish candle (close > open)"""
        return self.close > self.open
    
    @property
    def is_red(self) -> bool:
        """Bearish candle (close < open)"""
        return self.close < self.open
    
    @property
    def body(self) -> float:
        """Candle body size. Positive = green, Negative = red"""
        return self.close - self.open


class PullbackStrategy:
    """
    HTF Trend + LTF Pullback Strategy
    
    Pure strategy logic - no state, no execution, just signal generation.
    Same code used for both backtest and live trading.
    """
    
    def generate_signal(
        self, 
        ltf_candles: List[Candle], 
        htf_candles: List[Candle],
        position_open: bool = False
    ) -> Signal:
        """
        Generate trading signal based on multi-timeframe analysis
        
        Args:
            ltf_candles: List of closed LTF candles (chronologically ordered)
            htf_candles: List of closed HTF candles (chronologically ordered)
            position_open: Whether a position is currently open
            
        Returns:
            Signal.BUY, Signal.SELL, or Signal.HOLD
        """
        # Need at least 2 LTF candles and 1 HTF candle
        if len(ltf_candles) < 2 or len(htf_candles) < 1:
            return Signal.HOLD

        # Get relevant candles
        current_ltf = ltf_candles[-1]
        previous_ltf = ltf_candles[-2]
        current_htf = htf_candles[-1]

        # HTF must be green (uptrend filter)
        if not current_htf.is_green:
            return Signal.HOLD

        # Entry Logic: Pullback continuation pattern
        if not position_open:
            # Previous candle red (pullback) + Current candle green (buyers return)
            if previous_ltf.is_red and current_ltf.is_green:
                return Signal.BUY

        # Exit Logic: Momentum breaks
        if position_open:
            # Current candle turns red (sellers take control)
            if current_ltf.is_red:
                return Signal.SELL

        return Signal.HOLD