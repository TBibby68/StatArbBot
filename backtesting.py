import numpy as np
from signals import update_and_get_signal
import GlobalVariables
import pandas as pd
from EGinPythonBACKTEST import CointegrationBacktestQuery
from sqlalchemy import create_engine
from config import engine_string

# stocks we have data on to potentially trade = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]

# SECTION 1: DEFINING FUNCTIONS:

def compute_beta(stock1_prices, stock2_prices):
    """Compute the hedge ratio between 2 time series(stock prices).
        
        Args: 
            stock1_prices (series): The stream of stocks prices for one stock.
            stock2_prices (series): The stream of stock prices for a second stock.

        Returns:
            float: the computed beta (hedge ratio for our position).
    """

    cov_matrix = np.cov(stock1_prices, stock2_prices)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1]
    return beta

def get_window_id(time):
    """Retrieve the window_id corresponding to a specific time from our SQL table.
       
        Args: 
            time (int): The "time" in our backtesting engine (number of minutes from starting time).

        Returns:
            int: the window_id that corresponds to the given time in the cointegration_results table.
    """

    query = '''
    SELECT window_id
    FROM cointegration_results
    WHERE end_time = %s
    LIMIT 1
    '''
    params = (time,)
    window_id_array = pd.read_sql(query, con=engine, params=params)

    if not window_id_array.empty:
        window_id = int(window_id_array.iloc[0, 0])
    else:
        window_id = None 

    return window_id

def simulate_close_trade(stock1_price, stock2_price, current_pair_returns):
    """Calculates the resulting PnL of closing a position with the current stock prices.

        Args: 
            stock1_price (float): the current price of the first stock in the pair we are trading.
            stock2_price (float): the current price of the second stock we are trading.

        Returns:
            None.
    """
    GlobalVariables.number_of_signals += 1

    if GlobalVariables.z_scores[0] > 0: # previous z score
        # z positive: spread is too high → short A, long B
        stock1_trade = "buy"
        stock2_trade = "sell"
    else:
        # z negative: spread is too low → long A, short B
        stock1_trade = "sell"
        stock2_trade = "buy"
    
    # calculate the PnL for each stock separately
    if stock1_trade == "buy": 
        pnl_stock1 = (GlobalVariables.entry_price_stock1 - stock1_price) * abs(GlobalVariables.stock1_stock)
    else:  
        pnl_stock1 = (stock1_price - GlobalVariables.entry_price_stock1) * abs(GlobalVariables.stock1_stock)

    if stock2_trade == "sell": 
        pnl_stock2 = (stock2_price - GlobalVariables.entry_price_stock2) * abs(GlobalVariables.stock2_stock)
    else:  
        pnl_stock2 = (GlobalVariables.entry_price_stock2 - stock2_price) * abs(GlobalVariables.stock2_stock)

    # update the total PnL and add it to the series of PnLs
    pnl_total = pnl_stock1 + pnl_stock2
    GlobalVariables.cash += pnl_total
    GlobalVariables.trade_returns.append(pnl_total)
    current_pair_returns.append(pnl_total)

    # update the max profit / max drawdown from a single trade
    if pnl_total >= GlobalVariables.max_profit:
        GlobalVariables.max_profit = pnl_total
    elif pnl_total < GlobalVariables.max_drawdown:
        GlobalVariables.max_drawdown = pnl_total

    # reset the position
    GlobalVariables.stock1_stock = 0
    GlobalVariables.stock2_stock = 0

def simulate_open_trade(stock1_price, stock2_price, hedge_ratio):
    """Calculates the resulting PnL of opening a position with the current stock prices and hedge ratio.
    
        This function updates several Global Variables that keep track of the current PnL of the bot, and 
        the current open position(ie the amount of stock1 we are long and the stock2 that we are short).

        Args: 
            stock1_price (float): the current price of the first stock in the pair we are trading.
            stock2_price (float): the current price of the second stock we are trading.
            hedge_ratio (float): the hedge ratio between the 2 stocks (Return of "calculate_beta" function).

        Returns:
            None.
    """
    GlobalVariables.number_of_signals += 1
    if GlobalVariables.z_scores[-1] > 0: # testing the current z score
        # z positive: spread is too high → short A, long B
        GlobalVariables.stock1_stock -= 10 / stock1_price 
        GlobalVariables.stock2_stock += hedge_ratio * 10 / stock2_price
    else:
        # z negative: spread is too low → long A, short B
        GlobalVariables.stock1_stock += hedge_ratio * 10 / stock1_price 
        GlobalVariables.stock2_stock -= 10 / stock2_price 

    # keep track of the entry prices
    GlobalVariables.entry_price_stock1 = stock1_price
    GlobalVariables.entry_price_stock2 = stock2_price

def find_new_pair_and_close_current_position(window_id, engine, stock1_price, stock2_price, current_pair_returns):
    """Finds a new pair of stocks that is cointegrated and then closes out the current position of stocks that are
       no longer cointegrated.

        Args: 
            window_id (int): the current id (we will be running this function exclusively at the end of this window).
            engine (variable): the connection to the SQL database.
            stock1_price (float): the price of our first stock.
            stock2_price (float): the price of our second stock.
            current_pair_returns (series): The history of the PnL of this pair of stocks up to this point.

        Returns:
            DataFrame: the dataframe containing the new pair we wll trade on, and the p_value for the 
            hypothesis test.
    """

    # find the new pair to trade on and print information to terminal
    best_pair = CointegrationBacktestQuery(window_id, engine)
    print("the value of the previous pair was too high, this is the new current p_value: ", str(best_pair["p_value"][0]))

    # simulate the trade, reset the last_signal and return the pair
    if GlobalVariables.last_signal != "CLOSE":
        simulate_close_trade(stock1_price=stock1_price, stock2_price=stock2_price, current_pair_returns=current_pair_returns)
        GlobalVariables.last_signal = "CLOSE"

    return best_pair

def UpdateCurrentStockPair(best_pair):
    """Parse the best_pair dataframe into several variables we can use later.

        Args: 
            best_pair (DataFrame): the dataframe produced in the above function containing the p_value of the current
            best pair as per our cointegration test.

        Returns:
            List[string]: A list containing the two stock symbols as strings.
            string: The first stock symbol.
            string: The second stock symbol.
    """
    if best_pair is not None:
        print(best_pair)
        stock1 = best_pair.iloc[0, 0]
        stock2 = best_pair.iloc[0, 1]
        current_stock_pair = [stock1, stock2]
    else:
        # if the current pair is not cointegrated / there is no cointegrated pair, then return this as the pair
        current_stock_pair = ["", ""]

    print("this is the current pair we will trade on:", current_stock_pair)
    return current_stock_pair, stock1, stock2

def Calculate_Cointegrated_Pair(window_id, engine, current_stock_pair, stock1_price, stock2_price, current_pair_returns):
    """Query the database for the cointegration score of the current pair, and if there is no current pair, then find one.

        This function is similar to find_new_pair_and_close_current_position(), but with the difference 1 key difference: it 
        is meant to be ran every 2 weeks when we recalculate the cointegration relationship, whereas the previosuly mentioned 
        function ONLY runs when the relationship has already broken down, detected as such by this function.

        Args: 
            window_id (int): the current id (we will be running this function exclusively at the end of this window).
            engine (variable): the connection to the SQL database.
            stock1_price (float): the price of our first stock.
            stock2_price (float): the price of our second stock.
            current_pair_returns (series): The history of the PnL of this pair of stocks up to this point.

        Returns:
            DataFrame: the dataframe containing the new pair we wll trade on, and the p_value for the 
            hypothesis test.
    """

    # if we don't have a pair currently, find a pair and print the results to the terminal
    if current_stock_pair == ["", ""]:
        best_pair = CointegrationBacktestQuery(window_id, engine)
        print("this is the current p_value: ", str(best_pair["p_value"][0]))
    else: 
        # if we have a current pair, test if the relationship still exists
        best_pair = CointegrationBacktestQuery(window_id, engine, current_stock_pair)
        
        # close current position if the relationship break down, and find a new pair to trad eon
        if best_pair is None:
            best_pair = find_new_pair_and_close_current_position(window_id, engine, stock1_price, stock2_price, current_pair_returns)
        else:
            print("this is the current p_value: ", str(best_pair["p_value"][0]))

    return best_pair

def Pull_Last_3_Months_And_Next_2_Weeks(stock1, stock2):
    """Query the database for the prices of the currently traded stocks for the "next" 2 weeks(trading time),
        and the "last" 3 months(for hedge ratio calculation).

        Args: 
            stock1 (string): the symbol of our first stock.
            stock2 (string): the symbol of our second stock.

        Returns:
            DataFrame: the dataframe containing the prices of both stocks for the afformentioned timeframe.
    """

    # define the query
    columns = f'"{stock1}", "{stock2}", minute'
    query = f'''
    SELECT {columns}
    FROM backtesting_data
    WHERE minute > %s AND minute <= %s
    ''' 

    # run the query
    params = (end_time - 24000, end_time + 3900)
    stocks_df = pd.read_sql_query(query, con=engine, params=params)
    stocks_df["minute"] = stocks_df["minute"].astype(int)

    return stocks_df

# SECTION 2: INITIALISING VARIABLES AND CONNECTING TO THE DATABASE:

# The end_time corresponds to 24000 minutes after the starting time which is ~3 months. 
# stock1_price and stock2_price can be anything, as they are reset after the first iteration, and only used after that.
current_stock_pair = ["", ""]
engine = create_engine(engine_string)
end_time = 24000
GlobalVariables.last_signal = "CLOSE" 
stock1_price = 45230
stock2_price = 235
current_pair_returns = []

# SECTION 3: LOPPING THROUGH THE 3 MONTH PERIOD OF THE BACKTESTING DATA AND SIMULATING THE TRADING STRATEGY:

# here, the index 44k is roughly 2 weeks before the end of the data, meaning that we stop once we don't have the next 2 weeks of data to backtest on. 
while end_time <= 44000:

    # first get the current window we are in
    # if theres no current pair, then find one. If there is a current pair, test it, and if it doesn't meet the standard, find another one.
    # then parse the results into strings, 
    # and then finally query the backtesting database for the past 3 months and next 2 weeks of data for this pair.
    window_id = get_window_id(end_time)
    best_pair = Calculate_Cointegrated_Pair(window_id, engine, current_stock_pair, stock1_price, stock2_price, current_pair_returns)
    current_stock_pair, stock1, stock2 = UpdateCurrentStockPair(best_pair)
    stocks_df = Pull_Last_3_Months_And_Next_2_Weeks(stock1, stock2)

    # initalise this list so we can keep track of returns per-pair
    current_pair_returns = []

    # simulate the trading on the 2 weeks
    for _,row in stocks_df.iloc[24000:].iterrows():
        # pull the prices "currently" and then pull the series from "3 months ago" to "2 weeks ahead":
        stock1_price = row[stock1]
        stock2_price = row[stock2]
        current_minute = int(row["minute"])
        start_minute = current_minute - 24000
        mask = (stocks_df["minute"] >= start_minute) & (stocks_df["minute"] < current_minute)
        stock1_prices = stocks_df.loc[mask, stock1]
        stock2_prices = stocks_df.loc[mask, stock2]

        # calculate the hedge ratio and then the signal based on this
        beta = compute_beta(stock1_prices,stock2_prices)
        signal = update_and_get_signal(stock1_price, stock2_price, beta)

        # simulate the trade based on the signal
        if signal == "OPEN":
            simulate_open_trade(stock1_price, stock2_price, hedge_ratio=beta)
        elif signal == "CLOSE":
            simulate_close_trade(stock1_price, stock2_price, current_pair_returns)

    trade_returns_series = pd.Series(current_pair_returns)
    current_sharpe_ratio = trade_returns_series.mean() / trade_returns_series.std()
    print("this is the basic estimator of the sharpe ratio for the strategy: " + str(current_sharpe_ratio))

    # roll the time forward by 2 weeks: roughly 3900 trading minutes
    end_time += 3900

# SECTION 4: LOGGING PERFORMANCE METRICS OF THE BOT:

trade_returns_series = pd.Series(GlobalVariables.trade_returns)
sharpe_ratio = trade_returns_series.mean() / trade_returns_series.std()
print("Overall this is the current PnL of the past 6 months: " + str(GlobalVariables.cash))
print("this is the basic estimator of the sharpe ratio for the strategy: " + str(sharpe_ratio))
print("this is the most lost on a single trade: " + str(GlobalVariables.max_drawdown))
print("this is the most made on a single trade: " + str(GlobalVariables.max_profit))
print("the number of signals in this period is: " + str(GlobalVariables.number_of_signals))