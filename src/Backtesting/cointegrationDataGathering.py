import pandas as pd
from statsmodels.tsa.stattools import coint
import itertools
import pandas as pd
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
##############
# Parallelisation:

# this needs to be defined outside the main function so the parallelisation can work properly. If this was inside the main function then each interpreter would look in the file and fail to find the analyse_window function, and crash

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
    coint_window_size_mins = 24000
    trading_window_size_mins = 3900 # 2 weeks of trading minutes

    # Create connection engine using the private engine_string stored in our config file
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

#################

# this is the file that tests which stocks are cointegrated, but only on the backtesting data that we have stored locally in postgres
# this file generates a table in postgres that contains the start time, end time, both stocks, and then p value and t-stat for every 
# single combination of stock pairs and 2 week rooling time blocks in the 6 month testing period. 

# takes in list of stock tickers, and if one pair is cointegrated, it returns the last 3 months of the prices(from input time) +
# the next 2 weeks of the stocks, so we can "trade" on these 2 weeks. This doesn't work by time it purely works by the row index within the table
# start_time should start at 0 here for the full 6 months ago
# def CointegrationTestOnBigBanks(end_time, window_id, engine):

#     # Define time range: ~3 months: 24000 minutes of trading time corresponds to roughly 3 months
#     # the input is the end time, so in backtesting logic this is when we are calculating over the PAST three months, and then using that result to trade the NEXT 2 weeks
#     start_time = end_time - 24000

#     # This is the combination of ALL the stocks in the list above (dataframe)
#     backtesting_data = None

#     backtesting_data = pd.read_sql(f'SELECT * FROM backtesting_data OFFSET {start_time} LIMIT {end_time} ', engine)

#     # Loop over all unique pairs (ignoring the minute column)
#     tickers = backtesting_data.columns.drop("minute")
#     for stock1, stock2 in itertools.combinations(tickers, 2):
#         series1 = backtesting_data[stock1]
#         series2 = backtesting_data[stock2]

#         # Run Engle-Granger cointegration test
#         score, pvalue, _ = coint(series1, series2)

#         # list of dictionaries: each dictionary corresponds to one row in our test statistic table that we will be 
#         # drawing from.
#         database_row_dictionary = {
#             "window_id": window_id,
#             "start_time": start_time,
#             "end_time": end_time,
#             "stock1": f"{stock1}",
#             "stock2": f"{stock2}",
#             "p_value": pvalue,
#             "test_stat": score
#         }
        
#         df_row = pd.DataFrame([database_row_dictionary])  # Wrap in list to make a single-row DataFrame

#         # this will generate the table if it doesn't already exist
#         df_row.to_sql(
#             'cointegration_results', 
#             con=engine,
#             if_exists='append',
#             index=False              
#         )

#         # Read the contents of the table to verify
#         df_check = pd.read_sql('SELECT * FROM cointegration_results', con=engine)
#         print(df_check.tail())



# # Loop through each window and perform cointegration test
# for window_id in range(number_of_windows):
#     # call the cointegration function and add the rows to the new table
#     CointegrationTestOnBigBanks(coint_window_size_mins, window_id, engine)
    
#     # move the end_time up by 2 weeks
#     coint_window_size_mins += trading_window_size_mins