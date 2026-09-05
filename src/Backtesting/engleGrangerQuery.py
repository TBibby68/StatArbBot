import pandas as pd
from backtestConfig import BacktestConfig

def find_tradeable_pair(current_window_id, engine, open_trade):

    bconfig = BacktestConfig

    # If we already have a position, only check whether the incumbent pair is still eligible.
    if open_trade is not None:

        query = '''
                SELECT stock1, stock2, p_value
                FROM cointegration_results_energy
                WHERE window_id = %s
                  AND p_value < %s
                  AND stock1 = %s
                  AND stock2 = %s LIMIT 1 \
                '''

        params = (
            current_window_id,
            bconfig.eg_sig_level,
            open_trade.stock1,
            open_trade.stock2,
        )

    # Otherwise choose the best available pair.
    else:

        query = '''
                SELECT stock1, stock2, p_value
                FROM cointegration_results_energy
                WHERE window_id = %s
                  AND p_value < %s
                  AND stock1 <> 'minute'
                  AND stock2 <> 'minute'
                ORDER BY p_value ASC LIMIT 1 \
                '''

        params = (
            current_window_id,
            bconfig.eg_sig_level,
        )

    result = pd.read_sql(
        query,
        con=engine,
        params=params,
    )

    if result.empty:
        return None

    return result.iloc[0]