from enum import StrEnum
from dataclasses import dataclass
from dataclasses import asdict
import datetime

class TradeCloseMethod(StrEnum):
    SIGNAL = "signal"
    FORCED = "forced"

@dataclass
class TradeEntry:
    window_id: int
    stock1: str
    stock2: str
    entry_minute: int # remember this is not the actual timestamp but the integer tracker!
    entry_timestamp: datetime # THIS is the actual timestamp one
    entry_price_1: float
    entry_price_2: float
    entry_price_1_slipped: float
    entry_price_2_slipped: float
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

    exit_minute: int
    exit_timestamp: datetime
    exit_price_1: float
    exit_price_2: float
    exit_zscore: float | None
    
    gross_pnl: float
    gross_pnl_slipped : float
    cfd_costs: float
    transaction_costs: float
    net_pnl: float

    # so we can easily inject to sql without nesting errors
    def to_dict(self):
        return {
            **asdict(self.OpenLeg),
            "holding_minutes": self.holding_minutes,
            "exit_reason": self.exit_reason,
            "exit_minute": self.exit_minute,
            "exit_timestamp": self.exit_timestamp,
            "exit_price_1": self.exit_price_1,
            "exit_price_2": self.exit_price_2,
            "exit_zscore": self.exit_zscore,
            "gross_pnl": self.gross_pnl,
            "gross_pnl_slipped": self.gross_pnl_slipped,
            "transaction_costs": self.transaction_costs,
            "cfd_financing": self.cfd_costs,
            "net_pnl": self.net_pnl,
        }

class BacktestConfig:

    # thresholds
    entry_threshold = 3.5
    exit_threshold = 0.5

    # window config
    cointegration_window_size = 24000
    eg_sig_level = 0.05
    trading_window_size = 3900
    zscore_window_size = 100

    # trading config
    position_size = 100000 # 100k is comfortably high enough so we don't hit minimum commission costs
    force_close_at_window_end = True
    trade_multiple_pairs = False
    max_price_age = 5 # only generate new signals if there has been price updates within the last 5 mins.

    # trading frictions
    slippage_bps = 1
    cfd_commission_per_share = 0.005
    cfd_min_commission = 1.00
    cfd_margin_rate = 0.20

class DataConfig:
    tickers = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]
    start_date = "2022-08-02"
    end_date = "2026-08-02"