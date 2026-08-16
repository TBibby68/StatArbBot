from StatArbBot.config import API_KEY, API_SECRET, BASE_URL, engine_string
from alpaca_trade_api.rest import REST, TimeFrame
from sqlalchemy import create_engine
import numpy as np
import backtestConfig as config
# This file is where we pull the 6 months stock data for big banks and push it to a database: FOR BACKTESTING

# Create the API object: this uses a different API connection than the websocket connection that the stream uses. 
api = REST(API_KEY, API_SECRET, base_url=BASE_URL)

# define the initial list of stocks to test
initial_stock_batch = config.DataConfig.tickers

combined = None

start_date = config.DataConfig.start_date
end_date = config.DataConfig.end_date

for ticker in initial_stock_batch:

    bars = api.get_bars(
        ticker,
        TimeFrame.Minute,
        start=start_date,
        end=end_date,
        feed="iex"
    ).df

    # Rename the 'close' column to the ticker symbol
    df = bars[["close"]].rename(columns={"close": ticker})

    # Join it into the combined DataFrame
    if combined is None:
        combined = df
    else:
        # here it is important we use an outer join so we don't delete rows where one stock doesn't have any trades
        # for these rows we will forward fill for now
        combined = combined.join(df, how="outer")

# forward fill blank values
combined.ffill(inplace=True)
# Then fill backward to catch leading NaNs
combined.bfill(inplace=True)
# convert to log prices for cointegration testing
combined_signal_gen_data = np.log(combined)

# keep the timestamp column in here!
combined = combined.sort_index()
combined_signal_gen_data = combined_signal_gen_data.sort_index()
combined["timestamp"] = combined.index
combined_signal_gen_data["timestamp"] = combined_signal_gen_data.index

# add this in so we can connect it to the 2 backtesting tables
combined_signal_gen_data['minute'] = range(len(combined_signal_gen_data))
combined['minute'] = range(len(combined))

# Create SQLAlchemy engine: here postgres is the default database and postgres is also the owner of this database(user field here)
engine = create_engine(engine_string)

# NOTE: Rename the tables here to make sure they match what they're supposed to be.

# Push DataFrames to separate tables in postgres for signal generation (log prices) and actual prices (for backtest)
combined.to_sql('backtesting_data_prices', engine, if_exists='replace', index=False)
combined_signal_gen_data.to_sql('backtesting_data', engine, if_exists='replace', index=False)

print("data added to postgres!")