import pandas as pd
from statsmodels.tsa.stattools import coint
import pandas as pd
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from concurrent.futures import ProcessPoolExecutor, as_completed
import backtestConfig as config

# TODO: Make this function quicker so it can run in <1hr

# test cointegration on a single window
def analyse_window(args):
    window_id, window = args
    results = []

    print(f"Starting window {window_id}", flush=True)

    if window.empty:
        raise ValueError(f"Window {window_id} is empty")

    for stock_1, stock_2 in combinations(window.columns, 2):
        print(
            f"Window {window_id}: {stock_1}/{stock_2}",
            flush=True
        )

        test_stat, p_value, _ = coint(
            window[stock_1].to_numpy(),
            window[stock_2].to_numpy()
        )

        results.append({
            "window_id": window_id,
            "stock1": f"{stock_1}",
            "stock2": f"{stock_2}",
            "p_value": p_value,
            "test_stat": test_stat
        })

        print(f"Finished window {window_id}", flush=True)

    return results

def main():
    coint_window_size_mins = config.BacktestConfig.cointegration_window_size
    trading_window_size_mins = config.BacktestConfig.trading_window_size

    # Create connection engine
    engine = create_engine(engine_string)

    # ignore the minute column:
    backtesting_data = pd.read_sql(f'SELECT * FROM backtesting_data', engine).drop(columns=["minute"])
    total_mins = len(backtesting_data)

    number_of_windows = 1 + (
        (total_mins - coint_window_size_mins) // trading_window_size_mins
    )

    window_inputs = []
    start = 0

    for window_id in range(number_of_windows):
        end = start + coint_window_size_mins
        window = backtesting_data.iloc[start:end].copy()

        print(
            f"BUILDING window={window_id}, "
            f"start={start}, end={end}, shape={window.shape}"
        )
        window_inputs.append((window_id, window))
        start += trading_window_size_mins

    for window_id, window in window_inputs:
        print(f"SUBMITTING window={window_id}, shape={window.shape}")

    with ProcessPoolExecutor(max_workers=4) as executor:

        futures = {
            executor.submit(analyse_window, args): args[0]
            for args in window_inputs
        }

        nested_results = []

        for future in as_completed(futures):
            window_id = futures[future]

            try:
                result = future.result(timeout=600)
                nested_results.append(result)
                print(f"Completed window {window_id}")
            except Exception as exc:
                print(f"Window {window_id} failed: {exc}")
                raise

    results = [
        result
        for window_results in nested_results
        for result in window_results
    ]

    # this will generate the table if it doesn't already exist
    pd.DataFrame(results).to_sql(
        'cointegration_results', 
        con=engine,
        if_exists='append',
        index=False              
    )

    # Read the contents of the table to verify
    df_check = pd.read_sql('SELECT * FROM cointegration_results', con=engine)
    print(df_check.tail())

if __name__ == "__main__":
    main()