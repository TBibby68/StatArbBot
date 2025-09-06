import numpy as np
import pandas as pd
from config import engine_string
from sqlalchemy import create_engine, text

# this function calculates the volatility over the current window:
def CalculateRealisedVolatility(end_time, engine):
    # the start time should be 3 months before the end time like with th EG test
    start_time = end_time - 24000
    # pull the data from the database for the time period
    backtesting_data = pd.read_sql(f'SELECT * FROM backtesting_data OFFSET {start_time} LIMIT {end_time} ', engine)
    new_row_dict = {
        "minute": end_time
    }

    for column in backtesting_data.columns:
        if column in ("minute",):  # skip non-price columns
            continue
        price_series = backtesting_data[column]
        # compute the log returns:
        log_returns = np.log(price_series / price_series.shift(1)).dropna()
        # calculate the period level volatility:
        realized_vol = log_returns.std()
        # annualise the volatility:
        annualized_vol = realized_vol * np.sqrt(252)
        new_row_dict[column] = annualized_vol

    # push the data to the backtesting table:
    vol_df = pd.DataFrame([new_row_dict])
    vol_df.to_sql("realised_volatility_data", engine, index=False, if_exists="append")

# connect to the database and run the above function on the table:
end_time = 24000
engine = create_engine(engine_string)
# create a new table to store the volatilities
backtesting_data = pd.read_sql(f'SELECT * FROM backtesting_data', engine)
new_table_structure = backtesting_data.head(0)
new_table_structure.to_sql('realised_volatility_data', engine, index=False, if_exists='replace')

while end_time <= 44000:
    # call the cointegration function and add the rows to the new table
    CalculateRealisedVolatility(end_time, engine)
    # move the end_time up by 1 minute
    end_time += 1