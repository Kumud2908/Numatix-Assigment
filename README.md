# Multi-Timeframe Trading Strategy  
Backtesting and Live Execution Parity

## Overview

This project implements a deterministic multi-timeframe pullback trading strategy with an emphasis on execution correctness and consistency between historical backtesting and live trading.

The objective of this assignment is  to demonstrate:
- clean and modular architecture,
- disciplined execution logic,
- and close behavioral parity between backtest and live systems.

The same strategy logic is used without duplication in both environments.

---

## Strategy Logic

### Timeframes

- **Lower Timeframe (LTF)**: 1-minute candles  
  Used for precise entry and exit decisions.
- **Higher Timeframe (HTF)**: 5-minute candles, derived from LTF candles  
  Used as a directional trend filter.

### Entry Rules (BUY)

A long position is opened when all of the following conditions are satisfied:
1. The most recent confirmed HTF candle is bullish (close > open).
2. The previous LTF candle is bearish (pullback).
3. The current LTF candle turns bullish.
4. No position is currently open.

### Exit Rules (SELL)

A position is closed when:
1. The current LTF candle turns bearish.
2. A position is currently open.

### Position Sizing

- Fixed notional size of 100 USDT per trade.

The strategy is rule-based and deterministic, with no indicators or adaptive parameters.

---

## Architecture

### Single Source of Truth

All signal generation logic is implemented in a single strategy class:

Pullback Strategy (Strategy.py)


This class is reused directly by:
- the backtesting engine, and
- the live trading engine.

No strategy logic is duplicated across systems.

### Component Responsibilities

- strategy.py -> Core strategy logic (stateless)
- backtest.py -> Historical execution using backtesting.py
- live_trader.py -> Live execution using Binance Testnet REST API
- compare_trades.py -> Trade validation and comparison


The strategy itself is stateless.  
Position state and order execution are handled by the execution layer.

---

## Higher Timeframe Handling

HTF candles are only made available after they are fully closed.

- Five LTF candles are first aggregated into a pending HTF candle.
- The HTF candle becomes usable on the next LTF iteration.

This delayed availability is implemented identically in both backtest and live systems to prevent look-ahead bias and ensure consistent signal timing.

---

## Backtesting

- Backtesting is performed using the `backtesting.py` framework.
- Input data consists of 1-minute candles.
- HTF candles are derived internally using the same aggregation logic as live trading.
- All trades are recorded with entry and exit timestamps and prices.

Backtest results are written to: backtest_trades.csv


---

## Live Trading

- Live trading is executed on Binance Spot Testnet using the REST API.
- Market data is fetched using closed 1-minute candles.
- Execution follows a strict sequence: Market Data → Signal → Order → Fill


All executed trades are logged to: live_trades.csv


No hardcoded signals or execution shortcuts are used.

---

## Trade Validation

Trade validation focuses on logical consistency rather than exact mechanical equality.

Trades are considered matching if:
- trade direction matches,
- entry times are within a small tolerance window,
- exit times are within a small tolerance window.

Small differences due to network latency or candle close timing are acceptable.

Candle indices and HTF numbering are treated as diagnostic information and are not used as primary validation criteria.

Validation is performed using: campare_trades.py


---

## Logging and Observability

Both the backtest and live systems include structured logging to trace:
- candle ingestion,
- signal generation,
- order placement,
- trade entry and exit.

This makes it possible to follow the full lifecycle of each trade and diagnose discrepancies.

---

## Key Takeaways

- A single strategy implementation is shared across backtest and live trading.
- Higher timeframe data is handled with proper confirmation and delay.
- Live trading behavior closely matches backtest behavior within acceptable real-world tolerances.
- The system is designed to be reproducible, explainable, and verifiable.

---


# Setup and Installation

This project uses a Python virtual environment located in the parent directory.

### 1. Activate the virtual environment

From the project directory:

```bash
source ../venv/bin/activate

```
### 2. Install Dependencies
```bash
pip install -r requirements.txt

```
### 3. Environment Variables

- Live trading requires Binance Testnet API credentials.
- Set the following environment variables:
```
 
 BINANCE_API_KEY=your_testnet_api_key
 BINANCE_API_SECRET=your_testnet_api_secret

```

 Create a .env file of the  format given in the .env.example format

 lets go 






  


