from StatArbBot.config import API_KEY, API_SECRET, BASE_URL, engine_string
from alpaca_trade_api.rest import REST, TimeFrame
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine
# This file is where we pull the 6 months stock data for big banks and push it to a database: FOR BACKTESTING

# Create the API object: this uses a different API connection than the websocket connection that the stream uses. 
api = REST(API_KEY, API_SECRET, base_url=BASE_URL)

# define the initial list of stocks to test
initial_stock_batch = ["JPM", "BAC", "C", "GS", "MS", "WFC", "USB", "TFC", "PNC", "COF"]

combined = None

for ticker in initial_stock_batch:
    df = api.get_bars(
        ticker,
        TimeFrame.Minute,
        start=(datetime.today() - relativedelta(months=6)).strftime('%Y-%m-%d'),
        end=datetime.today().strftime('%Y-%m-%d'),
        feed="iex"
    ).df

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
# Then fill backward to catch leading NaNs
combined.bfill(inplace=True) 

# add this in so we can connect it to the 2 backtesting tables
combined['minute'] = range(len(combined))

# Create SQLAlchemy engine: here postgres is the default database and postgres is also the owner of this database(user field here)
engine = create_engine(engine_string)

# Push DataFrame to table
combined.to_sql('backtesting_data', engine, if_exists='append', index=False)

print("data added to postgres!")