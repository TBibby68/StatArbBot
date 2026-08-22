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

# Sort first
combined = combined.sort_index()

# Save genuine last-update timestamps BEFORE filling prices
stock_columns = combined.columns.tolist()

for stock in stock_columns:
    combined[f"{stock}_last_update"] = (
        combined.index.to_series()
        .where(combined[stock].notna())
        .ffill()
    )

# Now fill prices
combined[stock_columns] = combined[stock_columns].ffill()
combined[stock_columns] = combined[stock_columns].bfill()

# Create signal data from PRICE columns only
combined_signal_gen_data = np.log(
    combined[stock_columns]
)

# Keep timestamps
combined["timestamp"] = combined.index
combined_signal_gen_data["timestamp"] = (
    combined_signal_gen_data.index
)

# Observation index
combined["minute"] = range(len(combined))
combined_signal_gen_data["minute"] = range(
    len(combined_signal_gen_data)
)

# Create SQLAlchemy engine: here postgres is the default database and postgres is also the owner of this database(user field here)
engine = create_engine(engine_string)

# NOTE: Rename the tables here to make sure they match what they're supposed to be.

# Push DataFrames to separate tables in postgres for signal generation (log prices) and actual prices (for backtest)
combined.to_sql('backtesting_data_prices', engine, if_exists='replace', index=False)
combined_signal_gen_data.to_sql('backtesting_data', engine, if_exists='replace', index=False)

print("data added to postgres!")