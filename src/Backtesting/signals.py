import pandas as pd
import backtestConfig as config
from collections import defaultdict, deque

# this is the file that contain functions that generate the signal to trade

# Holds spread history internally: makes a double ended queue, keeping the most recent 100 elements and has automatic length control
spread_histories = defaultdict(
    lambda: deque(maxlen=config.BacktestConfig.zscore_window_size)
)

# need this so we dont use stale spread histories from when the hedge ratio was different
def reset_spread_histories():
    spread_histories.clear()

def compute_spread(price_a, price_b, beta):
    return price_a - beta * price_b

def get_signal(pair_key, price_a, price_b, open_trade, beta=1.0):

    # add the spread to the rolling last (100) values 
    spread = compute_spread(price_a, price_b, beta) # returning the spread itself
    pair_history = spread_histories[pair_key]
    pair_history.append(spread) 

    spread_series = pd.Series(pair_history)

    # also returning the mean and std of the spread
    rolling_mean = spread_series.rolling(window=30).mean()
    rolling_std = spread_series.rolling(window=30).std()

    zscore_series = (spread_series - rolling_mean) / rolling_std
    current_z = zscore_series.iloc[-1]

    previous_z = (
        zscore_series.iloc[-2]
        if len(zscore_series) >= 2
        else float("nan")
    )

    # only open a position if it has only just crossed the threshold
    crossed_entry_threshold = (
            pd.notna(previous_z)
            and abs(previous_z) <= config.BacktestConfig.entry_threshold < abs(current_z)
    )

    if crossed_entry_threshold and open_trade is None:
        return "OPEN", current_z, spread, rolling_mean, rolling_std

    elif (
        abs(current_z) < config.BacktestConfig.exit_threshold
        and open_trade is not None
    ):
        return "CLOSE", current_z, spread, rolling_mean, rolling_std

    return None, current_z, spread, rolling_mean, rolling_std