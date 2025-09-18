from collections import deque
import pandas as pd
from StatArbBot.Backtesting import GlobalVariables # this is so we don't have any circular imports

# this is the file that contain functions that generate the signal to trade

# Holds spread history internally: makes a double ended queue, keeping the most recent 100 elements and has automatic length control
spread_history = deque(maxlen=100)

def compute_spread(price_a, price_b, beta):
    return price_a - beta * price_b

def compute_zscore(spread_series, window=30):
    rolling_mean = spread_series.rolling(window=window).mean()
    rolling_std = spread_series.rolling(window=window).std()
    return (spread_series - rolling_mean) / rolling_std

def update_and_get_signal(price_a, price_b, beta=1.0):
    spread = compute_spread(price_a, price_b, beta)
    spread_history.append(spread) # add the spread to the rolling last 100 values 

    if len(spread_history) < 1:
        return None  # not enough data

    zscore_series = pd.Series(spread_history)
    z = compute_zscore(zscore_series).iloc[-1]
    GlobalVariables.z_scores.append(z) # add the score to the queue

    # Example signal logic: definitely needs some work: it's currently just entering and has no exit logic essentially
    if abs(z) > 1.5 and GlobalVariables.last_signal != "OPEN":
        # the further we get away from the threshold the riskier the signal is so we hedge by reducing the position size
        #position_size_factor = 1 / (abs(z) - 1.5)
        GlobalVariables.last_signal = "OPEN"
        return "OPEN" #, position_size_factor # this is the signal to buy into the swap
    elif abs(z) < 0.5 and GlobalVariables.last_signal == "OPEN": # can't start with a close!
        #position_size_factor = 1
        GlobalVariables.last_signal = "CLOSE"
        return "CLOSE" #, position_size_factor # this is the signal to close out the swap 
    
    return None, None
    # if neither of these is satisfied then we return nothing 
