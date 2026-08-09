import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string

# Your existing engine
# engine = create_engine(...)

engine = create_engine(engine_string)

# Read the logged data
logged_df = pd.read_sql(
    "SELECT * FROM backtesting_data ORDER BY minute",
    con=engine
)

# Copy so we don't modify the original
prices_df = logged_df.copy()

# Columns that should NOT be exponentiated
excluded_columns = ["minute"]

# If you later add timestamps, include them too:
# excluded_columns = ["minute", "timestamp"]

# Exponentiate all price columns
price_columns = [c for c in prices_df.columns if c not in excluded_columns]

prices_df[price_columns] = np.exp(prices_df[price_columns])

# Save to a new SQL table
prices_df.to_sql(
    "backtesting_data_prices",
    con=engine,
    if_exists="replace",
    index=False,
)

# Export to Excel
output_file = r"C:\Users\tbibb\Downloads\backtest_unlogged.xlsx"
prices_df.to_excel(
    output_file,
    index=False,
)

print("Done!")
print(f"Rows: {len(prices_df)}")
print(f"Columns converted: {len(price_columns)}")