import pandas as pd
from statsmodels.tsa.stattools import coint
import itertools
import pandas as pd
from sqlalchemy import create_engine
from ..config import engine_string
# PULL 6 MONTHS OF COINT DATA ON A 2 WEEK ROLLING BASIS: for live trading on cloud just run this for last 2 weeks, for backteating run full 
# 6 months. split this into 2 files

def main():
    # no backtesting so we should keep it simple
    def CointegrationTestOnBigBanks(end_time, engine):

        # Define time range: ~3 months: 24000 minutes of trading time corresponds to roughly 3 months
        # the input is the end time, so in backtesting logic this is when we are calculating over the PAST three months, and then using that result to trade the NEXT 2 weeks
        start_time = end_time - 24000

        # This is the combination of ALL the stocks in the list above (dataframe)
        last2_Weeks_price_data = None

        # in the actual bot we want to 
        last2_Weeks_price_data = pd.read_sql(f'SELECT * FROM crypto_price_data OFFSET {start_time} LIMIT {end_time} ', engine)

        # Loop over all unique pairs
        tickers = last2_Weeks_price_data.columns.tolist()
        for stock1, stock2 in itertools.combinations(tickers, 2):
            series1 = last2_Weeks_price_data[stock1]
            series2 = last2_Weeks_price_data[stock2]

            # Run Engle-Granger cointegration test
            score, pvalue, _ = coint(series1, series2)

            # list of dictionaries: each dictionary corresponds to one row in our test statistic table that we will be 
            # drawing from.
            database_row_dictionary = {
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
                'live_cointegration_results',
                con=engine,
                if_exists='append',
                index=False
            )

            # Read the contents of the table to verify
            df_check = pd.read_sql('SELECT * FROM live_cointegration_results', con=engine)
            print(df_check.tail())

    # Create connection engine using the private engine_string stored in our config file
    engine = create_engine(engine_string)
    # run on last 2 weeks(starter for bot)
    CointegrationTestOnBigBanks(43500, engine)

if __name__ == "__main__":
    main()