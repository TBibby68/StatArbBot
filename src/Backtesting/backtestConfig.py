
from enum import StrEnum

# potential methods to explore for calculating the hedge ratio. 
class HedgeRatioMethod(StrEnum):
    STATIC_OLS = "static_ols"
    ROLLING_OLS = "rolling_ols"
    EXPANDING_OLS = "expanding_ols"
    EWLS = "exponentially_weighted_ls"
    KALMAN = "kalman"
    TOTAL_LEAST_SQUARES = "total_least_squares"
    ROBUST = "robust_regression"

class BacktestConfig:
    # parameters we may want to change for different experiments/fine tuning:
    # TODO: put this in a config file.
    entry_threshold = 1
    exit_threshold = 0.5

    cointegration_window_size = 24000
    trading_window_size = 3900
    zscore_window_size = 100

    transaction_cost_bps = 0.0
    initial_capital = 10_000.0

    hedge_ratio_estimator = HedgeRatioMethod.KALMAN

    force_close_at_window_end = True