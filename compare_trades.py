import pandas as pd
from datetime import timedelta

# Configuration

MAX_TIME_DIFF = timedelta(minutes=2)

# Load trade data

backtest_trades = pd.read_csv("backtest_trades.csv")
live_trades = pd.read_csv("live_trades.csv")

for df in (backtest_trades, live_trades):
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])

print("\nTRADE MATCHING VALIDATION")
print("=" * 60)

matched = 0
checked = 0

# Validation logic

for _, live_trade in live_trades.iterrows():
    # Find closest backtest trade by entry time
    time_diffs = abs(backtest_trades["entry_time"] - live_trade["entry_time"])
    closest_idx = time_diffs.idxmin()
    bt_trade = backtest_trades.loc[closest_idx]

    entry_diff = abs(bt_trade["entry_time"] - live_trade["entry_time"])
    exit_diff = abs(bt_trade["exit_time"] - live_trade["exit_time"])
    
    print(f"\nLive trade entry: {live_trade['entry_time']}")
    
    # Direction must match
    if bt_trade["direction"] != live_trade["direction"]:
        print("Direction mismatch")
        break

    # Entry timing tolerance
    if entry_diff > MAX_TIME_DIFF:
        print(f"Entry time mismatch: {entry_diff}")
        break

    # Exit timing tolerance
    if exit_diff > MAX_TIME_DIFF:
        print(f"Exit time mismatch: {exit_diff}")
        break

    print("Direction match")
    print(f"Entry time difference: {entry_diff}")
    print(f"Exit time difference : {exit_diff}")

    matched += 1
    checked += 1
    
# Summary

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Validated live trades: {checked}")
print(f"Matched trades:        {matched}")

if matched == checked:
    print("Trade logic matches between backtest and live execution")
else:
    print("Trade logic divergence detected")
