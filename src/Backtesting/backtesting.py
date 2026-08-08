import numpy as np
from signals import update_and_get_signal
import GlobalVariables
import pandas as pd
from EGinPythonBACKTEST import CointegrationBacktestQuery
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
import importlib.metadata
import backtestConfig
try:
    from pykalman import KalmanFilter
except importlib.metadata.PackageNotFoundError:
    KalmanFilter = None

# stocks we have data on to potentially trade = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]

# SECTION 1: DEFINING FUNCTIONS:

# need to check whether this variable kalman filter stuff works with a single coint test every 2 weeks? I don't think it does. 
def update_kalman_beta(prev_beta, prev_cov, x_new, y_new, kf):
    """
    Update the Kalman filter for one new observation.
    
    Parameters
    ----------
    prev_beta : float
        Previous beta estimate.
    prev_cov : ndarray
        Previous state covariance matrix (1x1 matrix).
    x_new : float
        New stock1 price (the independent variable).
    y_new : float
        New stock2 price (the dependent variable). 
    kf : KalmanFilter
        A configured pykalman KalmanFilter object.
        
    Returns
    -------
    new_beta : float
        Updated beta estimate.
    new_cov : ndarray
        Updated state covariance matrix.
    """
    # reshape x_new into the required (1,1) observation matrix
    obs_matrix = np.array([[x_new]])

    # run one-step Kalman update
    new_state_mean, new_state_cov = kf.filter_update(
        filtered_state_mean = np.array([prev_beta]),
        filtered_state_covariance = prev_cov,
        observation = y_new,
        observation_matrix = obs_matrix
    )

    new_beta = new_state_mean[0]
    return new_beta, new_state_cov

def compute_beta_kalman_initial(stock1_prices, stock2_prices):
    """
    Estimate time-varying hedge ratio between two time series using Kalman filter.

    Returns:
        1) numpy array of beta estimates (same length as input series)
        2) covariance matrix so we can calculate the next beta iteratively
        3) the Kalman filter object
    """
    # convert the stock price series into arrays(a stack of T (1x1) arrays)
    X = stock1_prices.values.reshape(-1, 1, 1)
    y = stock2_prices.values

    # here we are modelling: y_t = H_t.x_t + e_t,
    # where H is our hedge ratio at time t (just a series of values in a linear regression instead of 1 constant value). 
    # the strategy for lower latency is to calculate this initially, but then only increment it every time step after that, so we don't
    # calculate the full 2 weeks of data every minute. The Kalman filter calculates based on the previos beta 

    kf = KalmanFilter(
        transition_matrices=[1],
        observation_matrices=X,
        initial_state_mean=0,
        initial_state_covariance=0.01,
        observation_covariance=25, # high = 25 / low <= 1 => less sensitive to volatility as it assumes more noise
        transition_covariance=0.01 # high = 0.1 => more sensitive to changes over time 
    )

    # for a string covariance relationship, we typically want the transition covariance to be low, observation to be high(but noisy data means a little higher), 
    # transition matrix to be 1, 0 initial state mean, initial state covariance small.
    
    state_means, state_covs = kf.filter(y)
    # gt the latest covariance matrix
    latest_covariance = state_covs[-1]
    beta_estimates = state_means[:, 0]
    # grab the latest hedge ratio to use for the signal generation
    latest_beta = beta_estimates[-1]
    print("this is the latest beta: ", latest_beta)
    return latest_beta, latest_covariance, kf

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

def simulate_close_trade(stock1_price, stock2_price, current_minute, closed_trades, open_trade, is_force_closure):
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

    # update the max profit / max drawdown from a single trade
    if pnl_total >= GlobalVariables.max_profit:
        GlobalVariables.max_profit = pnl_total
    elif pnl_total < GlobalVariables.max_drawdown:
        GlobalVariables.max_drawdown = pnl_total

    # reset the position
    GlobalVariables.stock1_stock = 0
    GlobalVariables.stock2_stock = 0

    # track the trade in our list
    closed_trades.append(
        backtestConfig.CompletedTrade(
            OpenLeg = open_trade,
            holding_minutes = current_minute - open_trade.entry_timestamp,
            exit_timestamp = current_minute,
            exit_reason = backtestConfig.TradeCloseMethod.FORCED if is_force_closure else backtestConfig.TradeCloseMethod.SIGNAL,
            exit_price_1 = stock1_price,
            exit_price_2 = stock2_price,
            exit_zscore = GlobalVariables.z_scores[0],
            gross_pnl = pnl_total,
            transaction_costs = 0, # hardcode as 0 for now, will model later
            net_pnl = pnl_total
            ))

def simulate_open_trade(window_id, stock1_price, stock2_price, hedge_ratio, current_minute, stock1, stock2):
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
    direction = "SHORT"
    if GlobalVariables.z_scores[-1] > 0: # testing the current z score
        # z positive: spread is too high → short A, long B
        GlobalVariables.stock1_stock -=  10 / stock1_price 
        GlobalVariables.stock2_stock += hedge_ratio * 10 / stock2_price
    else:
        direction = "LONG"
        # z negative: spread is too low → long A, short B
        GlobalVariables.stock1_stock += hedge_ratio * 10 / stock1_price 
        GlobalVariables.stock2_stock -= 10 / stock2_price

    # keep track of the entry prices
    GlobalVariables.entry_price_stock1 = stock1_price
    GlobalVariables.entry_price_stock2 = stock2_price

    # add an open trade object, which we will then complete to when we close the trade
    open_trade = backtestConfig.TradeEntry(
        window_id = window_id, 
        stock1 = stock1, 
        stock2 = stock2, 
        entry_timestamp = current_minute, 
        entry_price_1 = stock1_price, 
        entry_price_2 = stock2_price, 
        entry_zscore = GlobalVariables.z_scores[-1], 
        hedge_ratio_entry = hedge_ratio, 
        position_size_1 = GlobalVariables.stock1_stock, 
        position_size_2 = GlobalVariables.stock2_stock,
        direction = direction)
        # Added when we close the trade:
        # exit_timestamp =
        # exit_price_1 =
        # exit_price_2 =
        # exit_zscore =
        # hedge_ratio_exit =
        # exit_reason =
        # gross_pnl =
        # transaction_costs =
        # net_pnl =
        # holding_minutes =

    return open_trade

def find_new_pair_and_force_close(window_id, engine, stock1_price, stock2_price, current_minute, open_trade, completed_trades):
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
    
    if best_pair is not None:
        print("the value of the previous pair was too high, this is the new current p_value: ", str(best_pair["p_value"][0]))

    # simulate the trade, reset the last_signal and return the pair
    if GlobalVariables.last_signal != "CLOSE":
        simulate_close_trade(stock1_price=stock1_price, stock2_price=stock2_price, current_minute=current_minute, closed_trades=completed_trades, open_trade=open_trade, is_force_closure=True)
        GlobalVariables.last_signal = "CLOSE"
    # reset the kalman filter flag for the next pair
    GlobalVariables.ran_initial_kalman_filter = False
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

# NOTE: this function is currently fixed at a 3 month coint period, so don't try to edit that parameter before that has been changed. 
def Calculate_Cointegrated_Pair(window_id, engine, current_stock_pair, stock1_price, stock2_price, current_minute, open_trade, completed_trades):
    """Query the database for the cointegration score of the current pair, and if there is no current pair, then find one.

        This function is similar to find_new_pair_and_close_current_position(), but with the difference 1 key difference: it 
        is meant to be ran every 2 weeks when we recalculate the cointegration relationship, whereas the previosuly mentioned 
        function ONLY runs when the relationship has already broken down, detected as such by this function.

        Args: 
            window_id (int): the current id (we will be running this function exclusively at the end of this window).
            engine (variable): the connection to the SQL database.
            stock1_price (float): the price of our first stock.
            stock2_price (float): the price of our second stock.

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
        
        # close current position if the relationship break down, and find a new pair to trade on
        if best_pair is None:
            best_pair = find_new_pair_and_force_close(window_id, engine, stock1_price, stock2_price, current_minute=current_minute, open_trade=open_trade, completed_trades=completed_trades)
        else:
            print("this is the current p_value: ", str(best_pair["p_value"][0]))

    return best_pair

# SECTION 3: LOOPING THROUGH THE 3 MONTH PERIOD OF THE BACKTESTING DATA AND SIMULATING THE TRADING STRATEGY:

def run_backtest(
    data : pd.DataFrame,
    config : backtestConfig.BacktestConfig
):
    """
    Run the strategy only on the supplied data.

    """

    current_open_trade = None
    completed_trades: list[dict] = []
    GlobalVariables.last_signal = "CLOSE" 

    # stock1_price and stock2_price can be anything, as they are reset after the first iteration, and only used after that.
    stock1_price = 45230
    stock2_price = 235

    # this is the end date of the first trading period, (eg 3 months coint test + 2 weeks trading)
    trading_time = config.trading_window_size
    coint_window = config.cointegration_window_size
    window_end_time = coint_window + trading_time
    current_stock_pair = ["", ""]
    
    # TODO: make this calculated based on a proper calendar, not just an approx value
    final_trading_period = 3900
    window_id = 0

    # need to ensure we still time to trade, so every period is the same. 
    while window_end_time < len(data) - final_trading_period:

        # if there's no current pair, then find one. If there is a current pair, test it, and if it doesn't meet the standard, find another one.
        # then parse the results into strings, 
        # and then finally query the backtesting database for the full coint time + trading time of data for this pair.

        # it needs to be the previous window's result, as at this point that's all the information we have.
        best_pair = Calculate_Cointegrated_Pair(window_id, engine, current_stock_pair, stock1_price, stock2_price, 0, current_open_trade, completed_trades=completed_trades)

        # this window has no cointegrated pair, so we will move to the next window and try again.
        if best_pair is None:
            print("no cointegrated pair found for this window, moving to the next window")

            window_id += 1
            window_end_time += trading_time
            continue

        current_stock_pair, stock1, stock2 = UpdateCurrentStockPair(best_pair)

        # slice the data frame. NOTE: as it stands now the cointegration is only calculated at 3 month windows, so changing the coint_window parameter will make the backtest completely nonsensical until this has been fixed.
        stocks_df = data.loc[
            data["minute"].between(
                window_end_time - coint_window,
                window_end_time + trading_time,
                inclusive="right",
            ),
            [stock1, stock2, "minute"],
        ].copy()

        # simulate the trading on the period
        for _,row in stocks_df.iloc[trading_time:].iterrows():
            # pull the prices "currently" and then pull the series from "coint_window ago" to "trading_time ahead":
            stock1_price = row[stock1]
            stock2_price = row[stock2]
            current_minute = int(row["minute"])
            start_minute = current_minute - trading_time
            mask = (stocks_df["minute"] >= start_minute) & (stocks_df["minute"] < current_minute)
            stock1_prices = stocks_df.loc[mask, stock1]
            stock2_prices = stocks_df.loc[mask, stock2]

            # compute hedge ratio
            # TODO: add in introspection here so we can have another class to hold all the methods and call cleanly here
            beta = compute_beta(stock1_prices, stock2_prices)
            signal = update_and_get_signal(stock1_price, stock2_price, beta)

            # simulate the trade based on the signal
            if signal == "OPEN":
                print("Opening a position")
                current_open_trade = simulate_open_trade(window_id, stock1_price, stock2_price, hedge_ratio=beta, current_minute=current_minute, stock1=stock1, stock2=stock2)
            elif signal == "CLOSE":
                print("closing a position")
                simulate_close_trade(stock1_price, stock2_price, current_minute=current_minute, closed_trades=completed_trades, open_trade=current_open_trade, is_force_closure=False)

        # increment the window and time
        window_id += 1
        window_end_time += trading_time
    
    # push to postgres
    rows = [trade.to_dict() for trade in completed_trades]

    trades_df = pd.DataFrame(rows)

    trades_df.to_sql(
        "completed_trades",
        con=engine,
        if_exists="replace",
        index=False,
    )

# run the backtest on the postgres data
engine = create_engine(engine_string)

data = pd.read_sql('SELECT * FROM backtesting_data', con=engine)
backtest_config = backtestConfig.BacktestConfig()

run_backtest(data, backtest_config)