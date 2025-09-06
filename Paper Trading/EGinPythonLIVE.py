from config import API_KEY, API_SECRET, BASE_URL, stream_url, crypto_stream_url, CRYPTO_API_KEY, CRYPTO_SECRET
import numpy as np
from Backtesting.signals import update_and_get_signal # to get the trading signals
from alpaca_trade_api.rest import REST, TimeFrame
from datetime import datetime, timedelta
import pandas as pd
import Backtesting.GlobalVariables as GlobalVariables
from statsmodels.tsa.stattools import coint
import itertools
# this is the file that tests which stocks are cointegrated: but only on live data, so API calls are made in this file!

# takes in list of stock tickers, and if one pair is cointegrated, it returns the last 3 months of the prices(from input time) +
# the next 2 weeks of the stocks, so we can "trade" on these 2 weeks.
def CointegrationTestOnBigBanks(start_time, basket_of_stocks):
    api = REST(API_KEY, API_SECRET, base_url=BASE_URL)

    # Define time range: ~3 months
    end_time = start_time + timedelta(days=100)

    # This is the combination of ALL the stocks in the list above (dataframe)
    combined = None
    # This is the dataframe that holds the next 2 weeks of the most cointegrated stocks out of the list
    next2weeks = None

    # Get 1-minute bars for all stocks 
    for ticker in basket_of_stocks:
        df = api.get_bars(
            ticker,
            TimeFrame.Minute,
            start=start_time.strftime('%Y-%m-%d'),
            end=end_time.strftime('%Y-%m-%d'),
            feed="iex"
        ).df

        # print the date range to check it is correct
        print(df.index.min(), df.index.max())

        # Rename the 'close' column to the ticker symbol
        df = df[["close"]].rename(columns={"close": ticker})

        # Join it into the combined DataFrame
        if combined is None:
            combined = df
        else:
            # here it is important we use an outer join so we don't delete rows where one stock doesn't have any trades
            # for these rows we will forward fill for now
            combined = combined.join(df, how="outer")

    # forward fill blank values
    combined.ffill(inplace=True)
    combined.bfill(inplace=True)   # Then fill backward to catch leading NaNs

    # Store results in a list
    cointegration_results = []

    # Loop over all unique pairs
    tickers = combined.columns.tolist()
    for stock1, stock2 in itertools.combinations(tickers, 2):
        series1 = combined[stock1]
        series2 = combined[stock2]

        # Run Engle-Granger cointegration test
        score, pvalue, _ = coint(series1, series2)

        cointegration_results.append({
            "Pair": f"{stock1}-{stock2}",
            "p-value": pvalue,
            "test_stat": score
        })

    # Convert results to DataFrame
    results_df = pd.DataFrame(cointegration_results).sort_values(by="p-value")
    significant_results = results_df[results_df["p-value"] < 0.05]

    # Check if any rows meet the condition
    if not significant_results.empty:
        # Find the row with the minimum p-value
        best_row = significant_results.loc[significant_results["p-value"].idxmin()]
        
        # Get the 'pair' value from that row
        best_pair = best_row["Pair"]

        # Split the pair string into two tickers
        ticker1, ticker2 = best_pair.split("-")

        tickerPair = [ticker1, ticker2]

        # get the NEXT 2 weeks of the stock prices for the best pair: same logic as above but with different dates and just 2 stocks
        for ticker in tickerPair:
            df = api.get_bars(
                ticker,
                TimeFrame.Minute,
                start=end_time.strftime('%Y-%m-%d'),
                end=(end_time + timedelta(days=14)).strftime('%Y-%m-%d'),
                feed="iex"
            ).df

            # print the date range to check it is correct
            print(df.index.min(), df.index.max())

            # Rename the 'close' column to the ticker symbol
            df = df[["close"]].rename(columns={"close": ticker})

            # Join it into the combined DataFrame
            if next2weeks is None:
                next2weeks = df
            else:
                next2weeks = next2weeks.join(df, how="inner")

        # put net2weeks below combined to get the full history: the length og the "combined" df is where we will start "trading"/backtesting
        GlobalVariables.startIterationForBacktestingEngine = len(combined)
        combined_df = pd.concat([combined, next2weeks], ignore_index=True)

        # Extract the corresponding columns from the combined DataFrame
        best_pair_df = combined_df[[ticker1, ticker2]]
    else:
        best_pair = None
        best_pair_df = None 

    print("Best pair:", best_pair)

    return best_pair_df # this will be the input to the backtesting engine: the next 2 weeks + the testing period