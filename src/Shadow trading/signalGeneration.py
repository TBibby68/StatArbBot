from collections import deque
import pandas as pd
import StatArbBot.src.Backtesting.backtestConfig as config

# this is the file that contain functions that generate the signal to trade

def compute_spread(price_a, price_b, beta):
    return price_a - beta * price_b

def compute_zscore(spread_series, window=30):
    rolling_mean = spread_series.rolling(window=window).mean()
    rolling_std = spread_series.rolling(window=window).std()
    return (spread_series - rolling_mean) / rolling_std

# pass the spread history in so we can trade multiple pairs at once
def get_signal(
        price_a, 
        price_b, 
        open_trade, 
        spread_history, 
        beta=1.0):

    # add the spread to the rolling last 100 values 
    spread = compute_spread(price_a, price_b, beta)
    spread_history.append(spread) 

    if len(spread_history) < 1:
        return None  # not enough data

    zscore_series = pd.Series(spread_history)
    z = compute_zscore(zscore_series).iloc[-1]

    # threshold logic: TODO: make this configurable for the experiments
    if abs(z) > config.BacktestConfig.entry_threshold and open_trade is None:
        return "OPEN", z
    elif abs(z) < config.BacktestConfig.exit_threshold and open_trade is not None:
        return "CLOSE", z 
    
    # if neither of these is satisfied then we return nothing 
    return None, z