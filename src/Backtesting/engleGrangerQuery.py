import pandas as pd
import backtestConfig as config
# this is the file that queries which stocks are cointegrated from the backtesting data that we have stored locally in postgres

# this takes the current window id, sql engine, and the current stock pair as inputs and either returns None if the current pair is 
# not cointegrated over the window, or the pair if they are. If no pair is provided then it just queries the whole table
def find_tradeable_pairs(current_window_id, engine, current_stock_pair = None):

    bconfig = config.BacktestConfig
    cointegration_result = None # this will stay as None if either the current pair is no longer cointegrated, or there isn't any cointegrated pair
    # pull the cointegration results from the database 

    if bconfig.trade_multiple_pairs:
 
        query = '''
        SELECT stock1, stock2, p_value
        FROM cointegration_results
        WHERE window_id = %s
        AND p_value < %s
        AND stock1 <> 'minute'
        AND stock2 <> 'minute'
        ORDER BY p_value ASC
        '''
        params = (current_window_id, bconfig.eg_sig_level)
    else:
        if current_stock_pair != None:
            query = '''
            SELECT stock1, stock2, p_value 
            FROM cointegration_results 
            WHERE window_id = %s AND p_value < %s
            AND stock1 = %s AND stock2 = %s
            AND stock1 <> 'minute'
            AND stock2 <> 'minute'
            '''
            params = (current_window_id, bconfig.eg_sig_level, current_stock_pair[0], current_stock_pair[1])

        else:
            query = '''
            SELECT stock1, stock2, p_value
            FROM cointegration_results
            WHERE window_id = %s AND p_value < %s
            AND stock1 <> 'minute'
            AND stock2 <> 'minute'
            ORDER BY p_value ASC
            LIMIT 1
            '''
            params = (current_window_id, bconfig.eg_sig_level)

    cointegration_result = pd.read_sql(query, con=engine,params=params)

    # set to None if it is empty so the rest of the checks work
    if cointegration_result.empty:
        cointegration_result = None
    # return the result: if the current stock pair is still cointegrated, then we get it, and if we find a new one, we return it. 
    # if we can't find a cointegrated pair then we return None
    return cointegration_result