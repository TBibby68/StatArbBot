
from enum import StrEnum
from dataclasses import dataclass
from dataclasses import asdict

# potential methods to explore for calculating the hedge ratio. 
class HedgeRatioMethod(StrEnum):
    STATIC_OLS = "static_ols"
    ROLLING_OLS = "rolling_ols"
    EXPANDING_OLS = "expanding_ols"
    EWLS = "exponentially_weighted_ls"
    KALMAN = "kalman"
    TOTAL_LEAST_SQUARES = "total_least_squares"
    ROBUST = "robust_regression"

class TradeCloseMethod(StrEnum):
    SIGNAL = "signal"
    FORCED = "forced"

@dataclass
class TradeEntry:
    window_id: int
    stock1: str
    stock2: str
    entry_timestamp: int
    entry_price_1: float
    entry_price_2: float
    entry_zscore: float
    hedge_ratio_entry: float
    position_size_1: float
    position_size_2: float
    direction: str

@dataclass
class CompletedTrade:
    OpenLeg: TradeEntry

    holding_minutes: int
    exit_reason: str

    exit_timestamp: int
    exit_price_1: float
    exit_price_2: float
    exit_zscore: float | None
    
    gross_pnl: float
    transaction_costs: float
    net_pnl: float

    # so we can easily inject to sql without nesting errors
    def to_dict(self):
        return {
            **asdict(self.OpenLeg),
            "holding_minutes": self.holding_minutes,
            "exit_reason": self.exit_reason,
            "exit_timestamp": self.exit_timestamp,
            "exit_price_1": self.exit_price_1,
            "exit_price_2": self.exit_price_2,
            "exit_zscore": self.exit_zscore,
            "gross_pnl": self.gross_pnl,
            "transaction_costs": self.transaction_costs,
            "net_pnl": self.net_pnl,
        }

class BacktestConfig:
    # parameters we may want to change for different experiments/fine tuning:
    entry_threshold = 1.5
    exit_threshold = 0.5

    cointegration_window_size = 24000
    eg_sig_level = 0.05
    trading_window_size = 3900
    zscore_window_size = 100

    transaction_cost_bps = 1
    slippage_bps = 1
    initial_capital = 10_000.0

    hedge_ratio_estimator = HedgeRatioMethod.STATIC_OLS

    force_close_at_window_end = True

class DataConfig:
    tickers = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]
    start_date = "2022-08-01"
    end_date = "2025-08-01"