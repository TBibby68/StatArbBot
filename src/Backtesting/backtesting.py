from signals import get_signal
import pandas as pd
import numpy as np
from engleGrangerQuery import find_tradeable_pairs
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

def calculate_exposure(
    open_trade,
    current_price_1,
    current_price_2,
):
    exposure_1 = (
        open_trade.position_size_1
        * current_price_1
    )

    exposure_2 = (
        open_trade.position_size_2
        * current_price_2
    )

    gross_exposure = (
        abs(exposure_1)
        + abs(exposure_2)
    )

    long_exposure = (
        max(exposure_1, 0)
        + max(exposure_2, 0)
    )

    short_exposure = (
        abs(min(exposure_1, 0))
        + abs(min(exposure_2, 0))
    )

    return (
        gross_exposure,
        long_exposure,
        short_exposure,
    )

def simulate_close_trade(
        stock1_price, 
        stock2_price, 
        current_minute, 
        closed_trades, 
        open_trade, 
        is_force_closure, 
        zscore: float | None, # this will be None for forced closures as they are so rare
        stock1_age,
        stock2_age): 
    
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
            net_pnl = pnl_total_Slipped - transaction_costs,
            exit_price_age_1 = stock1_age,
            exit_price_age_2 = stock2_age
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

def find_new_pair_and_force_close(
        window_id, 
        engine, 
        stock1_price, 
        stock2_price, 
        current_minute, 
        open_trade, 
        completed_trades,
        stock1_age,
        stock2_age):

    # find the new pair to trade on and print information to terminal
    tradeable_pairs = find_tradeable_pairs(window_id, engine)
    
    if tradeable_pairs is not None:
        print("the value of the previous pair was too high, this is the new current p_value: ", str(tradeable_pairs["p_value"][0]))

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
            zscore=None,
            stock1_age=stock1_age,
            stock2_age=stock2_age)

    # return the current best pair and None: the current open trade is always going to be None after we close
    return tradeable_pairs, None

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
        stock1_age,
        stock2_age):

    # if we don't have a pair currently, find a pair and print the results to the terminal
    if current_stock_pair == ["", ""]:
        tradeable_pairs = find_tradeable_pairs(window_id, engine)
        print("this is the current p_value: ", str(tradeable_pairs["p_value"][0]))
    else: 
        # if we have a current pair, test if the relationship still exists
        tradeable_pairs = find_tradeable_pairs(window_id, engine, current_stock_pair)
        
        # close current position if the relationship break down, and find a new pair to trade on
        # this will never run if we have mutliple pairs - simpler!
        if tradeable_pairs is None:
            tradeable_pairs, open_trade = find_new_pair_and_force_close(
                window_id, 
                engine, 
                stock1_price, 
                stock2_price, 
                current_minute=current_minute, 
                open_trade=open_trade, 
                completed_trades=completed_trades,
                stock1_age=stock1_age,
                stock2_age=stock2_age)
        else:
            # this will run if the last window's pair is the same as the current pair. 
            print("this is the current p_value: ", str(tradeable_pairs["p_value"][0]))

    # open_trade will only not be None here if we:
    # 1) continue trading the same pair as the last window, and 
    # 2) carry over an open position across from one window to the next
    return tradeable_pairs, open_trade

def calculate_unrealised_pnl(
    open_trade,
    current_price_1,
    current_price_2
):
    pnl_1 = (
        current_price_1 - open_trade.entry_price_1
    ) * open_trade.position_size_1

    pnl_2 = (
        current_price_2 - open_trade.entry_price_2
    ) * open_trade.position_size_2

    return pnl_1 + pnl_2

def Prepare_Trading_Window(
        tradeable_pair, 
        current_minute, 
        cointegration_window_size, 
        trading_window_end,
        data,
        hedge_ratio):
    # prepare the data for trading on a given pair

    # parse the df
    stock1 = tradeable_pair[0]
    stock2 = tradeable_pair[1]

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
        [stock1, stock2, "minute", "timestamp",  f"{stock1}_last_update",
        f"{stock2}_last_update",],
    ].copy()

    # Calculate canonical log spread
    current_window_stocks_df["spread"] = (
        np.log(current_window_stocks_df[stock1])
        - hedge_ratio * np.log(current_window_stocks_df[stock2])
    )

    return backtestConfig.TradingPairWindow(stock1, stock2, hedge_ratio, current_window_stocks_df)

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
    current_stock_pair = ["", ""]
    open_trade = None
    mark_to_market_records = [] # list of dicts where each is indexed by the minute

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
        tradeable_pairs, open_trade = Calculate_Cointegrated_Pair(
            window_id=window_id, 
            engine=engine, 
            current_stock_pair=current_stock_pair, 
            stock1_price=stock1_price, 
            stock2_price=stock2_price, 
            current_minute=current_minute, # current_minute == trading_window_end - trading_window_size should always be true here !
            open_trade=open_trade, 
            completed_trades=completed_trades,
            stock1_age=0, # NOTE: these are hardcoded because we effectively never need to force close positions so we dont need to track the age of the prices
            stock2_age=0)

        # this window has no cointegrated pair, so we will move to the next window and try again.
        if tradeable_pairs is None:
            print("no cointegrated pair found for this window, moving to the next window")

            current_stock_pair = None
            window_id += 1
            trading_window_end += trading_window_size
            current_minute += trading_window_size
            continue

        # list of all the trade info for each eligable pair for this window
        pair_windows = []

        stock_pairs = tradeable_pairs[["stock1", "stock2"]].values.tolist()

        current_stock_pair = stock_pairs[0]

        # prepare the data for each pair we might want to trade on this window
        for pair in stock_pairs:
            pair_windows.append(Prepare_Trading_Window(pair, 
                                                       current_minute, 
                                                       cointegration_window_size, 
                                                       trading_window_end,
                                                       data,
                                                       hedge_ratio))

        # NOTE: "current_minute" at this point should still be the start of the trading window

        # calculate the signal for all eligable pairs:
        for window in pair_windows:

            # reset the open trade for this pair
            open_trade = None

            # simulate trading on the current window - this df is a df that contains only the current pair
            for _,row in window.trading_df.iterrows():

                # get the current prices and time
                stock1_price = row[window.stock1]
                stock2_price = row[window.stock2]
                current_minute = int(row["minute"])

                # check whether either stock is using a stale price
                current_timestamp = row["timestamp"]

                stock1_last_update = row[f"{window.stock1}_last_update"]
                stock2_last_update = row[f"{window.stock2}_last_update"]

                stock1_age = (
                    current_timestamp - stock1_last_update
                ).total_seconds() / 60

                stock2_age = (
                    current_timestamp - stock2_last_update
                ).total_seconds() / 60

                # calculate the signal
                signal, zscore = get_signal(
                    np.log(stock1_price), 
                    np.log(stock2_price), 
                    open_trade=open_trade, 
                    beta=window.hedge_ratio
                    )

                # simulate the trade based on the signal
                if (
                    signal == "OPEN" 
                    and stock1_age <= config.max_price_age 
                    and stock2_age <= config.max_price_age
                ):
                    print("Opening a position")
                    open_trade = simulate_open_trade(
                        window_id, 
                        stock1_price, 
                        stock2_price, 
                        hedge_ratio=window.hedge_ratio, 
                        current_minute=current_minute, 
                        stock1=window.stock1, 
                        stock2=window.stock2, 
                        zscore=zscore)
                                
                unrealised_pnl = 0

                if open_trade is not None:
                    unrealised_pnl = calculate_unrealised_pnl(
                        open_trade=open_trade,
                        current_price_1=stock1_price,
                        current_price_2=stock2_price
                    )

                    gross_exposure, long_exposure, short_exposure = (
                        calculate_exposure(
                            open_trade=open_trade,
                            current_price_1=stock1_price,
                            current_price_2=stock2_price,
                        )
                    )

                if signal == "CLOSE":
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
                        zscore=zscore,
                        stock1_age=stock1_age,
                        stock2_age=stock2_age)
                    
                    realised_trade = completed_trades[-1]
                    
                    open_trade = None

                    print(
                        "CLOSE CHECK",
                        current_minute,
                        "unrealised:", unrealised_pnl,
                        "realised:", realised_trade.gross_pnl
                    )

                elif open_trade is not None:
                    # calculate mark-to-market PnL
                    unrealised_pnl = calculate_unrealised_pnl(
                        open_trade=open_trade,
                        current_price_1=stock1_price,
                        current_price_2=stock2_price
                    )

                    gross_exposure, long_exposure, short_exposure = (
                        calculate_exposure(
                            open_trade=open_trade,
                            current_price_1=stock1_price,
                            current_price_2=stock2_price,
                        )
                    )

                    # add it to the list of mtm records - only persist if the trade remains open
                    mark_to_market_records.append({
                        "minute": current_minute,
                        "window_id": window_id,
                        "stock1": window.stock1,
                        "stock2": window.stock2,
                        "entry_timestamp": open_trade.entry_timestamp,
                        "unrealised_pnl": unrealised_pnl,
                        "gross_exposure": gross_exposure,
                        "long_exposure": long_exposure,
                        "short_exposure": short_exposure,
                    })

        # increment the window and time
        window_id += 1
        trading_window_end += trading_window_size
    
    # mtm postgres 
    mtm_df = pd.DataFrame(mark_to_market_records)

    portfolio_unrealised = (
        mtm_df
        .groupby("minute", as_index=False)["unrealised_pnl"]
        .sum()
    )

    portfolio_unrealised.to_sql(
        "mtm_pnls",
        con=engine,
        if_exists="replace",
        index=False,
    )

    # push to postgres
    rows = [trade.to_dict() for trade in completed_trades]

    trades_df = pd.DataFrame(rows)

    # Sum realised PnL by exit minute
    realised_by_minute = (
        trades_df
        .groupby("exit_timestamp", as_index=False)["net_pnl"]
        .sum()
        .rename(columns={
            "exit_timestamp": "minute",
            "net_pnl": "realised_pnl"
        })
    )

    # Combine realised and unrealised observations
    portfolio_pnl = pd.merge(
        portfolio_unrealised,
        realised_by_minute,
        on="minute",
        how="outer"
    )

    # Sort chronologically
    portfolio_pnl = portfolio_pnl.sort_values("minute")

    # Missing unrealised/realised values mean zero
    portfolio_pnl["unrealised_pnl"] = (
        portfolio_pnl["unrealised_pnl"].fillna(0)
    )

    portfolio_pnl["realised_pnl"] = (
        portfolio_pnl["realised_pnl"].fillna(0)
    )

    # Realised PnL persists after the trade closes
    portfolio_pnl["cumulative_realised_pnl"] = (
        portfolio_pnl["realised_pnl"].cumsum()
    )

    # Mark-to-market portfolio PnL
    portfolio_pnl["total_pnl"] = (
        portfolio_pnl["cumulative_realised_pnl"]
        + portfolio_pnl["unrealised_pnl"]
    )

    portfolio_pnl.to_sql(
        "portfolio_pnl",
        con=engine,
        if_exists="replace",
        index=False,
    )

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