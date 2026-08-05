
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

# populate these when we opne and then close a trade and do analysis on the resulting df.
class TradeEntry:
    window_id: int
    stock1: str
    stock2: str
    direction: str
    entry_timestamp: int
    exit_timestamp: int
    entry_price_1: float
    entry_price_2: float
    exit_price_1: float
    exit_price_2: float
    entry_zscore: float
    exit_zscore: float
    hedge_ratio_entry: float
    hedge_ratio_exit: float
    position_size_1: float
    position_size_2: float
    exit_reason: str
    gross_pnl: float
    transaction_costs: float
    net_pnl: float
    holding_minutes: int

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