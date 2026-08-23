import pandas as pd
import backtestConfig as config
from collections import defaultdict, deque

# this is the file that contain functions that generate the signal to trade

# Holds spread history internally: makes a double ended queue, keeping the most recent 100 elements and has automatic length control
spread_histories = defaultdict(
    lambda: deque(maxlen=config.BacktestConfig.zscore_window_size)
)

def compute_spread(price_a, price_b, beta):
    return price_a - beta * price_b

def compute_zscore(spread_series, window=30):
    rolling_mean = spread_series.rolling(window=window).mean()
    rolling_std = spread_series.rolling(window=window).std()
    return (spread_series - rolling_mean) / rolling_std

def get_signal(pair_key, price_a, price_b, open_trade, beta=1.0):

    # add the spread to the rolling last (100) values 
    spread = compute_spread(price_a, price_b, beta)
    pair_history = spread_histories[pair_key]
    pair_history.append(spread) 

    zscore_series = pd.Series(pair_history)
    z = compute_zscore(zscore_series).iloc[-1]

    # threshold logic: TODO: make this configurable for the experiments
    if abs(z) > config.BacktestConfig.entry_threshold and open_trade is None:
        return "OPEN", z
    elif abs(z) < config.BacktestConfig.exit_threshold and open_trade is not None:
        return "CLOSE", z 
    
    # if neither of these is satisfied then we return nothing 
    return None, z