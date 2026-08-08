from Backtesting import backtestConfig

def analyse_results(trades):

    forced_trades = [
        trade
        for trade in trades
        if trade.exit_reason == backtestConfig.TradeCloseMethod.FORCED
    ]

    signal_trades = [
        trade
        for trade in trades
        if trade.exit_reason != backtestConfig.TradeCloseMethod.FORCED
    ]

    forced_PnL_sum = sum(trade.net_pnl for trade in forced_trades)
    signal_PnL_sum = sum(trade.net_pnl for trade in signal_trades)

    forced_PnL_mean = (
        forced_PnL_sum / len(forced_trades)
        if forced_trades
        else 0
    )

    signal_PnL_mean = (
        signal_PnL_sum / len(signal_trades)
        if signal_trades
        else 0
    )

    print(f"forced PnL mean: {forced_PnL_mean}, forced PnL sum: {forced_PnL_sum}, PnL mean: {signal_PnL_mean}, PnL sum: {signal_PnL_sum}")