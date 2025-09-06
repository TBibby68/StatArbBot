import pandas as pd
from statsmodels.tsa.stattools import coint
import itertools
import pandas as pd
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
# PULL 6 MONTHS OF COINT DATA ON A 2 WEEK ROLLING BASIS: for live trading on cloud just run this for last 2 weeks, for backteating run full 
# 6 months. split this into 2 files

# this is the file that tests which stocks are cointegrated, but only on the backtesting data that we have stored locally in postgres
# this file generates a table in postgres that contains the start time, end time, both stocks, and then p value and t-stat for every 
# single combination of stock pairs and 2 week rooling time blocks in the 6 month testing period. 

# takes in list of stock tickers, and if one pair is cointegrated, it returns the last 3 months of the prices(from input time) +
# the next 2 weeks of the stocks, so we can "trade" on these 2 weeks. This doesn't work by time it purely works by the row index within the table
# start_time shouold start at 0 here for the full 6 months ago
def CointegrationTestOnBigBanks(end_time, window_id, engine):

    # Define time range: ~3 months: 24000 minutes of trading time corresponds to roughly 3 months
    # the input is the end time, so in backtesting logic this is when we are calculating over the PAST three months, and then using that result to trade the NEXT 2 weeks
    start_time = end_time - 24000

    # This is the combination of ALL the stocks in the list above (dataframe)
    backtesting_data = None

    backtesting_data = pd.read_sql(f'SELECT * FROM backtesting_data OFFSET {start_time} LIMIT {end_time} ', engine)

    # Loop over all unique pairs
    tickers = backtesting_data.columns.tolist()
    for stock1, stock2 in itertools.combinations(tickers, 2):
        series1 = backtesting_data[stock1]
        series2 = backtesting_data[stock2]

        # Run Engle-Granger cointegration test
        score, pvalue, _ = coint(series1, series2)

        # list of dictionaries: each dictionary corresponds to one row in our test statistic table that we will be 
        # drawing from.
        database_row_dictionary = {
            "window_id": window_id,
            "start_time": start_time,
            "end_time": end_time,
            "stock1": f"{stock1}",
            "stock2": f"{stock2}",
            "p_value": pvalue,
            "test_stat": score
        }

        df_row = pd.DataFrame([database_row_dictionary])  # Wrap in list to make a single-row DataFrame

        # this will generate the table if it doesn't already exist
        df_row.to_sql(
            'cointegration_results', 
            con=engine,
            if_exists='append',
            index=False              
        )

        # Read the contents of the table to verify
        df_check = pd.read_sql('SELECT * FROM cointegration_results', con=engine)
        print(df_check.tail())

end_time = 24000
window_id = 0

# Create connection engine using the private engine_string stored in our config file
engine = create_engine(engine_string)

while end_time <= 44000:
    # call the cointegration function and add the rows to the new table
    CointegrationTestOnBigBanks(end_time, window_id, engine)
    # incrememnt the window_id
    window_id += 1
    # move the end_time up by 2 weeks
    end_time += 3900