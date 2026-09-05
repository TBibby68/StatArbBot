from collections import deque
from typing import Any

import numpy as np
import pandas as pd
from pandas import Series
from sqlalchemy import create_engine

import backtestConfig
from Backtesting.backtestConfig import BacktestConfig
from cfd_modelling import calculate_cfd_costs
from config import engine_string
from engleGrangerQuery import find_tradeable_pair
from signals import get_signal, calculate_spread_stats

def apply_slippage(price, position_size, slippage_bps):
    slippage_rate = slippage_bps / 10000

    if position_size > 0:   # buy
        return price * (1 + slippage_rate)
    else:                   # sell
        return price * (1 - slippage_rate)

def compute_hedge_ratio(stock1_prices, stock2_prices):

    # OLS hedge ratio: beta = Cov(stock1, stock2) / Var(stock2)
    cov_matrix = np.cov(stock1_prices, stock2_prices)
    hedge_ratio = cov_matrix[0, 1] / cov_matrix[1, 1]

    return hedge_ratio

def calculate_position_state(
    open_trade,
    current_price_1,
    current_price_2,
):
    # MTM PnL
    unrealised_pnl = calculate_unrealised_pnl(
        open_trade=open_trade,
        current_price_1=current_price_1,
        current_price_2=current_price_2,
    )

    # exposure
    gross_exposure, long_exposure, short_exposure = calculate_exposure(
        open_trade=open_trade,
        current_price_1=current_price_1,
        current_price_2=current_price_2,
    )

    return (
        unrealised_pnl,
        gross_exposure,
        long_exposure,
        short_exposure,
    )

def calculate_exposure(
    open_trade,
    current_price_1,
    current_price_2,
):
    # calc exposure of each leg
    exposure_1 = (
        open_trade.position_size_1
        * current_price_1
    )

    exposure_2 = (
        open_trade.position_size_2
        * current_price_2
    )

    # gross, long, and short
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
        current_datetime,
        closed_trades, 
        open_trade, 
        is_force_closure, 
        zscore: float | None, # this will be None for forced closures as they are so rare
        ):
    
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

    # calculate the gross PnL for each stock (AFTER slippage for both legs)
    pnl_stock1_Slipped = (
        exit_price_1_slipped - open_trade.entry_price_1_slipped
    ) * open_trade.position_size_1

    pnl_stock2_Slipped = (
        exit_price_2_slipped - open_trade.entry_price_2_slipped
    ) * open_trade.position_size_2

    pnl_total_slipped = pnl_stock1_Slipped + pnl_stock2_Slipped

    # estimate the cfd commission costs
    cfd_costs = calculate_cfd_costs(
        open_trade=open_trade
    )

    cfd_net_pnl = (
        pnl_total_slipped
        - cfd_costs.total_cost
    )

    exit_reason = (
        backtestConfig.TradeCloseMethod.FORCED
        if is_force_closure
        else backtestConfig.TradeCloseMethod.SIGNAL
    )

    # track the trade in our list
    closed_trades.append(
        backtestConfig.CompletedTrade(
            OpenLeg = open_trade,
            holding_minutes = current_datetime - open_trade.entry_timestamp,
            exit_minute = current_minute,
            exit_timestamp = current_datetime,
            exit_reason = exit_reason,
            exit_price_1 = stock1_price,
            exit_price_2 = stock2_price,
            exit_zscore = zscore,
            gross_pnl = pnl_total,
            gross_pnl_slipped = pnl_total_slipped,
            transaction_costs = 0, # just hardcoding. In the next commit make it so we can switch between cfds and cash equity models
            cfd_costs = cfd_costs.total_cost,
            net_pnl = cfd_net_pnl,
            )
    )

def simulate_open_trade(
    window_id,
    stock1_price,
    stock2_price,
    hedge_ratio,
    current_minute,
    current_timestamp,
    stock1,
    stock2,
    zscore
):

    config = backtestConfig.BacktestConfig

    # position size is before slippage because we are buying a number of shares
    if zscore > 0:
        # z positive: spread is too high → short A, long B
        direction = "SHORT"
        stock1_stock = - config.position_size / stock1_price
        stock2_stock = hedge_ratio * config.position_size / stock2_price
    else:
        # z negative: spread is too low → long A, short B
        direction = "LONG"
        stock1_stock = config.position_size / stock1_price
        stock2_stock = - hedge_ratio * config.position_size / stock2_price

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

    # create the open trade object
    return backtestConfig.TradeEntry(
        window_id = window_id, 
        stock1 = stock1, 
        stock2 = stock2, 
        entry_minute = current_minute, 
        entry_timestamp = current_timestamp,
        entry_price_1 = stock1_price, 
        entry_price_2 = stock2_price, 
        entry_price_1_slipped = entry_price_1_slipped, 
        entry_price_2_slipped = entry_price_2_slipped, 
        entry_zscore = zscore, 
        hedge_ratio_entry = hedge_ratio, 
        position_size_1 = stock1_stock, 
        position_size_2 = stock2_stock,
        direction = direction
    )

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

def save_backtest_results(
        completed_trades: list[dict[Any, Any]],
        config: BacktestConfig,
        mark_to_market_records: list[Any],
        spread_history: deque[Any]
):
    # Convert backtest outputs to DataFrames
    spread_history_df = pd.DataFrame(spread_history)
    mtm_df = pd.DataFrame(mark_to_market_records)
    trades_df = pd.DataFrame(
        [trade.to_dict() for trade in completed_trades]
    )

    # Save raw outputs
    spread_history_df.to_sql(
        "spread_history",
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

    # Aggregate portfolio state by timestamp
    portfolio_state = (
        mtm_df
        .groupby("timestamp", as_index=False)[
            [
                "unrealised_pnl",
                "gross_exposure",
                "long_exposure",
                "short_exposure",
            ]
        ]
        .sum()
    )

    # Aggregate realised PnL by exit timestamp
    realised_pnl = (
        trades_df
        .groupby("exit_timestamp", as_index=False)["net_pnl"]
        .sum()
        .rename(columns={
            "exit_timestamp": "timestamp",
            "net_pnl": "realised_pnl",
        })
    )

    # Combine realised and unrealised portfolio state
    portfolio_pnl = (
        portfolio_state
        .merge(
            realised_pnl,
            on="timestamp",
            how="outer",
        )
        .sort_values("timestamp")
    )

    # Missing observations represent zero exposure / PnL
    fill_zero_columns = [
        "unrealised_pnl",
        "realised_pnl",
        "gross_exposure",
        "long_exposure",
        "short_exposure",
    ]

    portfolio_pnl[fill_zero_columns] = (
        portfolio_pnl[fill_zero_columns].fillna(0)
    )

    # Calculate portfolio-level metrics
    portfolio_pnl["cumulative_realised_pnl"] = (
        portfolio_pnl["realised_pnl"].cumsum()
    )

    portfolio_pnl["total_pnl"] = (
            portfolio_pnl["cumulative_realised_pnl"]
            + portfolio_pnl["unrealised_pnl"]
    )

    portfolio_pnl["cfd_margin_required"] = (
            portfolio_pnl["gross_exposure"]
            * config.cfd_margin_rate
    )

    portfolio_pnl["capital_required"] = (
            portfolio_pnl["cfd_margin_required"]
            - portfolio_pnl["total_pnl"]
    )

    # Save portfolio outputs
    portfolio_pnl.to_sql(
        "portfolio_pnl",
        con=engine,
        if_exists="replace",
        index=False,
    )

def prices_are_fresh(
        current_timestamp,
        row: Series,
        stock1,
        stock2,
        max_price_age,
) -> bool:

    # return true if the latest price of both stocks was updated at most max_price_age mins ago
    stock1_last_update = row[f"{stock1}_last_update"]
    stock2_last_update = row[f"{stock2}_last_update"]

    stock1_age = (
             current_timestamp - stock1_last_update
     ).total_seconds() / 60

    stock2_age = (
             current_timestamp - stock2_last_update
     ).total_seconds() / 60

    return (
            stock1_age <= max_price_age
            and stock2_age <= max_price_age
    )


def run_backtest(
        data: pd.DataFrame,
        config: backtestConfig.BacktestConfig
):
    """
    Run the strategy only on the supplied data, and populate a pandas DataFrame with the resulting trades.

    """

    # Initialise variables
    window_id = 0
    open_trade = None
    current_pair = None
    stock1_price = None
    stock2_price = None

    # Output / diagnostics
    completed_trades: list[dict] = []
    mark_to_market_records = []

    # full history for post-mortem analysis
    spread_diagnostics: list[dict] = []

    # only the last few observations, and reset after every window
    rolling_spreads = deque(maxlen=config.zscore_window_size)

    # Window configuration
    trading_window_size = config.trading_window_size
    cointegration_window_size = config.cointegration_window_size
    current_minute = cointegration_window_size
    trading_window_end = cointegration_window_size + trading_window_size

    current_timestamp = data["timestamp"].iloc[0]

    # While we still have [2 weeks] to trade on
    while trading_window_end + trading_window_size < len(data):

        # 1. If there is no current pair we are trading on, then prefer to stick with that if it still cointegrated
        # 2. Otherwise, pick the best pair by p_value

        selected_pair = find_tradeable_pair(
            window_id,
            engine,
            open_trade,
        )

        pair_changed = selected_pair != current_pair

        # 3. If there is an open position only close it if we are switching pairs for this window
        if pair_changed and open_trade is not None:
            print("closing out the current position because the pair is no longer cointegrated")
            simulate_close_trade(
                stock1_price=stock1_price,
                stock2_price=stock2_price,
                current_minute=current_minute,
                current_datetime=current_timestamp,
                closed_trades=completed_trades,
                open_trade=open_trade,
                is_force_closure=True,
                zscore=None,
            )

            open_trade = None

        current_pair = selected_pair

        # this window has no cointegrated pair, so we will move to the next window and try again.
        if current_pair is None:
            print("no cointegrated pair found for this window, moving to the next window")
            trading_window_end += trading_window_size
            current_minute += trading_window_size
            window_id += 1
            continue

        # parse the stocks for easy access
        stock1 = current_pair[0]
        stock2 = current_pair[1]

        # prepare the df we will iterate over for this trading window
        columns = [
            *current_pair,
            "minute",
            "timestamp",
            *(f"{stock}_last_update" for stock in current_pair),
        ]

        current_window_df = data.loc[
            data["minute"].between(
                current_minute,
                trading_window_end,
                inclusive="right",
            ),
            columns,
        ].copy()

        # safety check to avoid time travel bugs
        assert current_window_df["minute"].is_monotonic_increasing

        # clear the spread history before we start the new window
        rolling_spreads.clear()

        # get the df lookback period to calculate the hedge ratio
        cointegration_df = data.loc[
            data["minute"].between(
                current_minute - cointegration_window_size,
                current_minute,
                inclusive="right",
            ),
            [stock1, stock2, "minute"],
        ].copy()

        # calculate a static hedge ratio for the trading period (eg 2 weeks)
        hedge_ratio = compute_hedge_ratio(
            np.log(cointegration_df[stock1]),
            np.log(cointegration_df[stock2]),
        )

        print(f"starting trading {window_id} on {stock1}/{stock2}")

        # iterate over the minutes in the current trading window
        for _, row in current_window_df.iterrows():

            # minute is the integer that defines the window, and timestamp is the actual time the data is taken from
            current_minute = int(row["minute"])
            current_timestamp = row["timestamp"]

            # Completely skip this minute if the data is stale
            if not prices_are_fresh(
                    current_timestamp,
                    row,
                    stock1,
                    stock2,
                    config.max_price_age,
            ): continue

            # calculate the spread we will be trading on this window
            stock1_price = row[stock1]
            stock2_price = row[stock2]

            # get a few useful spread stats
            spread, spread_mean, spread_std, current_z, previous_z = calculate_spread_stats(
                rolling_spreads,
                stock1_price,
                stock2_price,
                hedge_ratio,
            )

            # Calculate the signal for the current pair
            signal = get_signal(
                current_z,
                previous_z,
                open_trade,
            )

            # update the spread history for the current pair
            spread_diagnostics.append({
                "timestamp": current_timestamp,
                "window_id": window_id,
                "stock1": stock1,
                "stock2": stock2,
                "hedge_ratio": hedge_ratio,
                "stock1_price": stock1_price,
                "stock2_price": stock2_price,
                "spread": spread,
                "rolling_mean": spread_mean,
                "rolling_std": spread_std,
                "zscore": current_z,
            })

            # Open a position
            if signal == "OPEN":

                print(f"opening a position")
                open_trade = simulate_open_trade(
                    window_id=window_id,
                    stock1_price=stock1_price,
                    stock2_price=stock2_price,
                    hedge_ratio=hedge_ratio,
                    current_minute=current_minute,
                    current_timestamp=current_timestamp,
                    stock1=stock1,
                    stock2=stock2,
                    zscore=current_z,
                )

            # Close the position
            elif signal == "CLOSE":

                print("closing a position")
                simulate_close_trade(
                    stock1_price=stock1_price,
                    stock2_price=stock2_price,
                    current_minute=current_minute,
                    current_datetime=current_timestamp,
                    closed_trades=completed_trades,
                    open_trade=open_trade,
                    is_force_closure=False,
                    zscore=current_z,
                )

                open_trade = None

            # Calculate mark to market PnL of the position
            if open_trade is not None:
                # unrealised PnL and exposure stats
                unrealised_pnl, gross_exposure, long_exposure, short_exposure = calculate_position_state(
                    open_trade=open_trade,
                    current_price_1=stock1_price,
                    current_price_2=stock2_price,
                )

                # add it to the list
                mark_to_market_records.append({
                    "timestamp": current_timestamp,
                    "window_id": window_id,
                    "stock1": open_trade.stock1,
                    "stock2": open_trade.stock2,
                    "entry_timestamp": open_trade.entry_timestamp,
                    "unrealised_pnl": unrealised_pnl,
                    "gross_exposure": gross_exposure,
                    "long_exposure": long_exposure,
                    "short_exposure": short_exposure,
                })

        # increment the window
        trading_window_end += trading_window_size
        window_id += 1

    # save the results to Postgres for analysis
    save_backtest_results(
        completed_trades,
        config,
        mark_to_market_records,
        spread_diagnostics
    )

engine = create_engine(engine_string)

# get the raw price data to run the strategy on
price_data = pd.read_sql(
    """
    SELECT *
    FROM backtesting_data_prices_energy
    ORDER BY minute
    """,
    con=engine
)

# safety check to avoid time travel bugs
assert price_data["minute"].is_monotonic_increasing
assert price_data["timestamp"].is_monotonic_increasing

run_backtest(price_data, backtestConfig.BacktestConfig())