from signals import get_signal
import pandas as pd
import numpy as np
from engleGrangerQuery import CointegrationBacktestQuery
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
import backtestConfig

# SECTION 1: DEFINING FUNCTIONS: generalising for multiple pairs

def apply_slippage(price, position_size, slippage_bps):
    slippage_rate = slippage_bps / 10000

    if position_size > 0:   # buy
        return price * (1 + slippage_rate)
    else:                   # sell
        return price * (1 - slippage_rate)

def hedge_ratio(stock1_prices, stock2_prices):
    """Compute the hedge ratio between 2 time series(stock prices).
        
        Args: 
            stock1_prices (series): The stream of stocks prices for one stock.
            stock2_prices (series): The stream of stock prices for a second stock.

        Returns:
            float: the computed beta (hedge ratio for our position).
    """

    cov_matrix = np.cov(stock1_prices, stock2_prices)
    ratio = cov_matrix[0, 1] / cov_matrix[1, 1]

    return ratio

def simulate_close_trade(
        stock1_price, 
        stock2_price, 
        current_minute, 
        closed_trades, 
        open_trade, 
        is_force_closure, 
        zscore: float | None): # this will be None for forced closures as they are so rare
    """Calculates the resulting PnL of closing a position with the current stock prices.

        Args: 
            stock1_price (float): the current price of the first stock in the pair we are trading.
            stock2_price (float): the current price of the second stock we are trading.

        Returns:
            None.
    """
    config = backtestConfig.BacktestConfig

    # estimate slippage costs
    exit_price_1_slipped = apply_slippage(
        stock1_price,
        -open_trade.position_size_1,
        config.slippage_bps,
    )

    exit_price_2_slipped = apply_slippage(
        stock2_price,
        -open_trade.position_size_2,
        config.slippage_bps,
    )

    # calculate the gross PnL for each stock (BEFORE slippage)
    pnl_stock1 = (
        stock1_price - open_trade.entry_price_1
    ) * open_trade.position_size_1

    pnl_stock2 = (
        stock2_price - open_trade.entry_price_2
    ) * open_trade.position_size_2

    pnl_total = pnl_stock1 + pnl_stock2

    # calculate the gross PnL for each stock (AFTER slippage for BOTH open and close legs)
    pnl_stock1_Slipped = (
        exit_price_1_slipped - open_trade.entry_price_1_slipped
    ) * open_trade.position_size_1

    pnl_stock2_Slipped = (
        exit_price_2_slipped - open_trade.entry_price_2_slipped
    ) * open_trade.position_size_2

    pnl_total_Slipped = pnl_stock1_Slipped + pnl_stock2_Slipped

    # estimate transaction costs for each stock and leg 
    cost_rate = config.transaction_cost_bps / 10000

    # opening transaction cots
    open_notional = (
        abs(open_trade.position_size_1 * open_trade.entry_price_1_slipped)
        + abs(open_trade.position_size_2 * open_trade.entry_price_2_slipped)
    )

    # closing transaction costs (position size is fixed)
    close_notional = (
        abs(open_trade.position_size_1 * open_trade.entry_price_1_slipped)
        + abs(open_trade.position_size_2 * open_trade.entry_price_2_slipped)
    )

    transaction_costs = (open_notional + close_notional) * cost_rate

    # track the trade in our list
    closed_trades.append(
        backtestConfig.CompletedTrade(
            OpenLeg = open_trade,
            holding_minutes = current_minute - open_trade.entry_timestamp,
            exit_timestamp = current_minute,
            exit_reason = backtestConfig.TradeCloseMethod.FORCED if is_force_closure else backtestConfig.TradeCloseMethod.SIGNAL,
            exit_price_1 = stock1_price,
            exit_price_2 = stock2_price,
            exit_zscore = zscore,
            gross_pnl = pnl_total,
            gross_pnl_slipped = pnl_total_Slipped,
            transaction_costs = transaction_costs,
            net_pnl = pnl_total_Slipped - transaction_costs
            ))

def simulate_open_trade(
        window_id, 
        stock1_price, 
        stock2_price, 
        hedge_ratio, 
        current_minute, 
        stock1, 
        stock2, 
        zscore):
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

    config = backtestConfig.BacktestConfig

    # calculate the position size based on the market price with NO slippage
    # NOTE: the spread is calculated ONE WAY, meaning the trades have to be exact opposites of each other 
    if zscore > 0:
        # z positive: spread is too high → short A, long B
        direction = "SHORT"
        stock1_stock = - 10 / stock1_price 
        stock2_stock = hedge_ratio * 10 / stock2_price
    else:
        # z negative: spread is too low → long A, short B
        direction = "LONG"
        stock1_stock = 10 / stock1_price
        stock2_stock = - hedge_ratio * 10 / stock2_price 

    # estimate slippage costs on the position size
    entry_price_1_slipped = apply_slippage(
        stock1_price,
        stock1_stock,
        config.slippage_bps,
    )

    entry_price_2_slipped = apply_slippage(
        stock2_price,
        stock2_stock,
        config.slippage_bps,
    )

    # add an open trade object, which we will then complete to when we close the trade
    open_trade = backtestConfig.TradeEntry(
        window_id = window_id, 
        stock1 = stock1, 
        stock2 = stock2, 
        entry_timestamp = current_minute, 
        entry_price_1 = stock1_price, 
        entry_price_2 = stock2_price, 
        entry_price_1_slipped = entry_price_1_slipped, 
        entry_price_2_slipped = entry_price_2_slipped, 
        entry_zscore = zscore, 
        hedge_ratio_entry = hedge_ratio, 
        position_size_1 = stock1_stock, 
        position_size_2 = stock2_stock,
        direction = direction)

    return open_trade

def find_new_pair_and_force_close(window_id, engine, stock1_price, stock2_price, current_minute, open_trade, completed_trades, current_window_stocks_df, current_pair):
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

    # simulate the trade and return the pair. This would be None if you have closed out the pair from the last window, AND the relationship has broken down
    if open_trade is not None:

        assert open_trade is not None, (
            f"CLOSE signal with no open trade. Window={window_id}"
        )

        assert current_minute >= open_trade.entry_timestamp, (
            f"TIME TRAVEL!\n"
            f"Window={window_id}\n"
            f"entry_window={open_trade.window_id}, "
            f"Entry={open_trade.entry_timestamp}\n"
            f"Exit/current={current_minute}\n"
            f"Entry z={open_trade.entry_zscore}\n"
        ) 

        simulate_close_trade(
            stock1_price=stock1_price, 
            stock2_price=stock2_price, 
            current_minute=current_minute, 
            closed_trades=completed_trades, 
            open_trade=open_trade, 
            is_force_closure=True, 
            zscore=None)

    # return the current best pair and None: the current open trade is always going to be None after we close
    return best_pair, None

# NOTE: this function is currently fixed at a 3 month coint period, so don't try to edit that parameter before that has been changed. 
def Calculate_Cointegrated_Pair(
        window_id, 
        engine, 
        current_stock_pair, 
        stock1_price: float | None, 
        stock2_price: float | None, 
        current_minute, 
        open_trade, 
        completed_trades, 
        current_window_stocks_df):
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
            best_pair, open_trade = find_new_pair_and_force_close(
                window_id, 
                engine, 
                stock1_price, 
                stock2_price, 
                current_minute=current_minute, 
                open_trade=open_trade, 
                completed_trades=completed_trades, 
                current_window_stocks_df=current_window_stocks_df, 
                current_pair=current_stock_pair)
        else:
            # this will run if the last window's pair is the same as the current pair. 
            print("this is the current p_value: ", str(best_pair["p_value"][0]))

    # open_trade will only not be None here if we:
    # 1) continue trading the same pair as the last window, and 
    # 2) carry over an open position across from one window to the next
    return best_pair, open_trade

# SECTION 2: backtest function:

def run_backtest(
    data : pd.DataFrame,
    config : backtestConfig.BacktestConfig
):
    """
    Run the strategy only on the supplied data, and populate a pandas DataFrame with the resulting trades.

    """
    
    # Initialise variables
    completed_trades: list[dict] = []
    stock1_price = None
    stock2_price = None
    window_id = 0
    current_window_stocks_df = pd.DataFrame
    current_stock_pair = ["", ""]
    open_trade = None

    spread_volatility_window = pd.DataFrame(columns=[
        "window_id",
        "timestamp",
        "stock1",
        "stock2",
        "hedge_ratio",
        "spread_volatility",
    ])

    # eg 3 months coint test + 2 weeks trading
    trading_window_size = config.trading_window_size
    cointegration_window_size = config.cointegration_window_size
    trading_window_end = cointegration_window_size + trading_window_size
    current_minute = trading_window_end - trading_window_size

    # While we still have [2 weeks] to trade on
    while trading_window_end + trading_window_size < len(data):

        print(
            f"WINDOW {window_id} | "
            f"start={trading_window_end - trading_window_size} | "
            f"open_trade_entry="
            f"{None if open_trade is None else open_trade.entry_timestamp}"
        )

        # test for what the best pair to trade on for this window is, and if there is a position still open on a pair that is no longer cointegrated for the current window, we close that position out, and update the current pair to trade on.
        best_pair, open_trade = Calculate_Cointegrated_Pair(
            window_id=window_id, 
            engine=engine, 
            current_stock_pair=current_stock_pair, 
            stock1_price=stock1_price, 
            stock2_price=stock2_price, 
            current_minute=current_minute, # current_minute == trading_window_end - trading_window_size should always be true here !
            open_trade=open_trade, 
            completed_trades=completed_trades, 
            current_window_stocks_df=current_window_stocks_df)

        # this window has no cointegrated pair, so we will move to the next window and try again.
        if best_pair is None:
            print("no cointegrated pair found for this window, moving to the next window")

            window_id += 1
            trading_window_end += trading_window_size
            current_minute += trading_window_size
            continue

        # parse the df
        stock1 = best_pair.iloc[0, 0]
        stock2 = best_pair.iloc[0, 1]
        current_stock_pair = [stock1, stock2]

        # get the df for the cointegration lookback period (eg 3 months)
        cointegration_df = data.loc[
            data["minute"].between(
                current_minute - cointegration_window_size,
                current_minute,
                inclusive="right",
            ),
            [stock1, stock2, "minute"],
        ].copy()

        # calculate a static hedge ratio for the trading period (eg 2 weeks)
        hedge_ratio = hedge_ratio(
            np.log(cointegration_df[stock1]),
            np.log(cointegration_df[stock2]),
        )

        # get the df for the prices in the trading period (eg 2 weeks)
        current_window_stocks_df = data.loc[
            data["minute"].between(
                current_minute,
                trading_window_end,
                inclusive="right",
            ),
            [stock1, stock2, "minute", "timestamp"],
        ].copy()

        # Calculate canonical log spread
        current_window_stocks_df["spread"] = (
            np.log(current_window_stocks_df[stock1])
            - hedge_ratio * np.log(current_window_stocks_df[stock2])
        )

        # Spread volatility across this trading window
        spread_volatility = current_window_stocks_df["spread"].std()

        # One diagnostic row for this window
        spread_volatility_window.loc[len(spread_volatility_window)] = {
            "window_id": window_id,
            "timestamp": current_window_stocks_df["timestamp"].iloc[0],
            "stock1": stock1,
            "stock2": stock2,
            "hedge_ratio": hedge_ratio,
            "spread_volatility": spread_volatility
        }

        # NOTE: "current_minute" at this point should still be the start of the trading window

        # simulate trading on the current window
        for _,row in current_window_stocks_df.iterrows():
            # get the current prices and time
            stock1_price = row[stock1]
            stock2_price = row[stock2]
            current_minute = int(row["minute"])

            # calculate the signal
            signal, zscore = get_signal(np.log(stock1_price), np.log(stock2_price), open_trade=open_trade, beta=hedge_ratio)

            # simulate the trade based on the signal
            if signal == "OPEN":
                print("Opening a position")
                open_trade = simulate_open_trade(
                    window_id, 
                    stock1_price, 
                    stock2_price, 
                    hedge_ratio=hedge_ratio, 
                    current_minute=current_minute, 
                    stock1=stock1, 
                    stock2=stock2, 
                    zscore=zscore)
                
            elif signal == "CLOSE":
                assert open_trade is not None, (
                    f"CLOSE signal with no open trade. Window={window_id}"
                )

                assert current_minute >= open_trade.entry_timestamp, (
                    f"TIME TRAVEL!\n"
                    f"Window={window_id}\n"
                    f"entry_window={open_trade.window_id}, "
                    f"Entry={open_trade.entry_timestamp}\n"
                    f"Exit/current={current_minute}\n"
                    f"Entry z={open_trade.entry_zscore}\n"
                    f"Exit z={zscore}"
                )    

                print("closing a position")

                simulate_close_trade(
                    stock1_price, 
                    stock2_price, 
                    current_minute=current_minute, 
                    closed_trades=completed_trades, 
                    open_trade=open_trade, 
                    is_force_closure=False, 
                    zscore=zscore)
                
                open_trade = None

        # increment the window and time
        window_id += 1
        trading_window_end += trading_window_size
    
    # push to postgres
    rows = [trade.to_dict() for trade in completed_trades]

    trades_df = pd.DataFrame(rows)

    trades_df.to_sql(
        "completed_trades",
        con=engine,
        if_exists="replace",
        index=False,
    )

    spread_volatility_window.to_sql(
        "volatility_table",
        con=engine,
        if_exists="replace",
        index=False,
    )

# Implementation

engine = create_engine(engine_string)

# ensure we do not sample from the log prices used to generate the signal!

data = pd.read_sql(
    """
    SELECT *
    FROM backtesting_data_prices 
    ORDER BY minute
    """,
    con=engine
)

assert data["minute"].is_monotonic_increasing
print(data["minute"].duplicated().sum())
print(data["minute"].min())
print(data["minute"].max())
print(len(data))

backtest_config = backtestConfig.BacktestConfig()

run_backtest(data, backtest_config)