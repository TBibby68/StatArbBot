import pandas as pd
import backtestConfig as config
import numpy as np

def calculate_spread_stats(
    spread_history,
    stock1_price,
    stock2_price,
    hedge_ratio,
):
    # update the spread history with the current spread
    spread = (
        np.log(stock1_price)
        - hedge_ratio * np.log(stock2_price)
    )

    spread_history.append(spread)

    # calc the mean and standard deviation of the spread
    spread_series = pd.Series(spread_history)

    rolling_mean = spread_series.rolling(window=30).mean()
    rolling_std = spread_series.rolling(window=30).std()

    # calc the current and previous z scores
    zscore_series = (
        (spread_series - rolling_mean)
        / rolling_std
    )

    spread_mean = rolling_mean.iloc[-1]
    spread_std = rolling_std.iloc[-1]
    current_z = zscore_series.iloc[-1]

    previous_z = (
        zscore_series.iloc[-2]
        if len(zscore_series) >= 2
        else float("nan")
    )

    return (
        spread,
        spread_mean,
        spread_std,
        current_z,
        previous_z,
    )

def get_signal(current_z, previous_z, open_trade):

    # if we have ONLY JUST cross the threshold
    crossed_entry_threshold = (
        pd.notna(previous_z)
        and abs(previous_z) <= config.BacktestConfig.entry_threshold
        < abs(current_z)
    )

    # only open a trade if there isn't one already open
    if crossed_entry_threshold and open_trade is None:
        return "OPEN"

    if (
        open_trade is not None
        and abs(current_z) < config.BacktestConfig.exit_threshold
    ):
        return "CLOSE"

    return None