import os
import pandas as pd
from statsmodels.tsa.stattools import coint
from sqlalchemy import create_engine
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

from StatArbBot.config import engine_string
import backtestConfig as config


# ============================================================
# Worker globals
# ============================================================

PRICE_DATA = None
STOCK_NAMES = None


def initialise_worker(price_data, stock_names):
    """
    Called once when each worker process starts.

    This avoids passing an entire DataFrame with every individual
    cointegration-window task.
    """
    global PRICE_DATA
    global STOCK_NAMES

    PRICE_DATA = price_data
    STOCK_NAMES = stock_names


# ============================================================
# Cointegration
# ============================================================

def analyse_window(args):
    """
    Run Engle-Granger cointegration tests for every stock pair
    within one training window.

    args:
        tuple(window_id, start, end)
    """
    window_id, start, end = args

    window = PRICE_DATA[start:end]

    if window.shape[0] == 0:
        raise ValueError(
            f"Window {window_id} is empty "
            f"(start={start}, end={end})"
        )

    results = []

    number_of_stocks = window.shape[1]

    for i, j in combinations(range(number_of_stocks), 2):

        stock_1 = STOCK_NAMES[i]
        stock_2 = STOCK_NAMES[j]

        series_1 = window[:, i]
        series_2 = window[:, j]

        test_stat, p_value, _ = coint(
            series_1,
            series_2
        )

        results.append(
            {
                "window_id": window_id,
                "stock1": stock_1,
                "stock2": stock_2,
                "p_value": p_value,
                "test_stat": test_stat,
            }
        )

    return window_id, results


# ============================================================
# Main
# ============================================================

def main():

    coint_window_size_mins = (
        config.BacktestConfig.cointegration_window_size
    )

    trading_window_size_mins = (
        config.BacktestConfig.trading_window_size
    )

    engine = create_engine(engine_string)

    print("Loading backtesting data...")

    # We don't need the minute counter for the cointegration calculation.
    backtesting_data = pd.read_sql(
        "SELECT * FROM backtesting_data",
        con=engine
    ).drop(columns=["minute"])

    # Ensure numeric data
    backtesting_data = backtesting_data.astype(float)

    stock_names = backtesting_data.columns.tolist()

    # NumPy is cheaper to slice/process than repeatedly passing pandas objects.
    price_data = backtesting_data.to_numpy()

    total_mins = len(price_data)

    print(
        f"Loaded {total_mins:,} rows "
        f"for {len(stock_names)} stocks."
    )

    number_of_windows = 1 + (
        (total_mins - coint_window_size_mins)
        // trading_window_size_mins
    )

    if number_of_windows <= 0:
        raise ValueError(
            "Not enough data to construct a single "
            "cointegration window."
        )

    print(f"Number of windows: {number_of_windows}")

    # --------------------------------------------------------
    # Build only lightweight window coordinates
    # --------------------------------------------------------

    window_inputs = []

    start = 0

    for window_id in range(number_of_windows):

        end = start + coint_window_size_mins

        # Guard against incomplete final window
        if end > total_mins:
            break

        window_inputs.append(
            (window_id, start, end)
        )

        start += trading_window_size_mins

    print(
        f"Submitting {len(window_inputs)} "
        f"cointegration windows..."
    )

    # --------------------------------------------------------
    # Multiprocessing
    # --------------------------------------------------------

    max_workers = min(4, os.cpu_count() or 1)

    nested_results = []

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=initialise_worker,
        initargs=(price_data, stock_names),
    ) as executor:

        # chunksize > 1 reduces task-dispatch overhead.
        mapped_results = executor.map(
            analyse_window,
            window_inputs,
            chunksize=2,
        )

        for completed_count, (window_id, result) in enumerate(
            mapped_results,
            start=1,
        ):
            nested_results.append(result)

            print(
                f"Completed window {window_id} "
                f"({completed_count}/{len(window_inputs)})"
            )

    # --------------------------------------------------------
    # Flatten
    # --------------------------------------------------------

    results = [
        result
        for window_results in nested_results
        for result in window_results
    ]

    results_df = pd.DataFrame(results)

    print(
        f"Generated {len(results_df):,} "
        f"cointegration results."
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    results_df.to_sql(
        "cointegration_results",
        con=engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
    )

    print("Results written to cointegration_results.")

    # Optional verification
    df_check = pd.read_sql(
        """
        SELECT *
        FROM cointegration_results
        ORDER BY window_id DESC
        LIMIT 10
        """,
        con=engine,
    )

    print(df_check)


if __name__ == "__main__":
    main()