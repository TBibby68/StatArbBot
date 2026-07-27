import pandas as pd
# this is the file that queries which stocks are cointegrated from the backtesting data that we have stored locally in postgres

# this takes the current window id, sql engine, and the current stock pair as inputs and either returns None if the current pair is 
# not cointegrated over the window, or the pair if they are. If no pair is provided then it just queries the whole table
def CointegrationBacktestQuery(current_window_id, engine, current_stock_pair = None):

    cointegration_result = None # this will stay as None if either the current pair is no longer cointegrated, or there isn't any cointegrated pair
    # pull the cointegration results from the database 
    if current_stock_pair != None:
        query = '''
        SELECT stock1, stock2, p_value 
        FROM cointegration_results 
        WHERE window_id = %s AND p_value < 0.1
        AND stock1 = %s AND stock2 = %s
        '''
        params1 = (current_window_id, current_stock_pair[0], current_stock_pair[1])
        cointegration_result = pd.read_sql(query, con=engine,params=params1)
    else:
        query = '''
        SELECT stock1, stock2, p_value
        FROM cointegration_results
        WHERE window_id = %s AND p_value < 0.1
        ORDER BY p_value ASC
        LIMIT 1
        '''
        params2 = (current_window_id,)
        # this will contain the pair that is cointegrated from the 10 if there are any (for this specific time block in the database)
        cointegration_result = pd.read_sql(query, con=engine, params=params2)

    # set to None if it is empty so the rest of the checks work
    if cointegration_result.empty:
        cointegration_result = None
    # return the result: if the current stock pair is still cointegrated, then we get it, and if we find a new one, we return it. 
    # if we can't find a cointegrated pair then we return None
    return cointegration_result

# on preliminary test, the big banks in this list seem to have much stronger cointegration relationships than apple and microsoft, 
# with BAC/C giving a p score of 0.006478 in one test, whereas on the same day, AAPL/MSFT gave 0.96, which is a big difference!
# we will nwow see if making this change results in better returns 