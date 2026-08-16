# class BacktestConfig:
#     # parameters we may want to change for different experiments/fine tuning:
#     entry_threshold = 3.5
#     exit_threshold = 0.5

#     cointegration_window_size = 24000
#     eg_sig_level = 0.05
#     trading_window_size = 3900
#     zscore_window_size = 100

#     transaction_cost_bps = 1
#     slippage_bps = 1

#     hedge_ratio_estimator = HedgeRatioMethod.STATIC_OLS

#     force_close_at_window_end = True

# class DataConfig:
#     tickers = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]
#     start_date = "2025-08-02"
#     end_date = "2026-08-02"