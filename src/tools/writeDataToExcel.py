import pandas as pd
from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string

# Your existing engine
# engine = create_engine(...)

engine = create_engine(engine_string)

print(f"Connected to: {engine.url}")

with engine.connect() as conn:

    # Check table exists
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'completed_trades'
        );
    """)).scalar()

    print(f"Table exists: {exists}")

    if exists:

        # Read the whole table
        trades_df = pd.read_sql(
            "SELECT * FROM completed_trades",
            con=engine
        )

        # Save to Excel
        output_file = r"C:\Users\tbibb\Downloads\completed_trades.xlsx"
        trades_df.to_excel(output_file, index=False)

        print(f"Exported {len(trades_df)} rows to '{output_file}'")

    else:
        print("Table 'completed_trades' not found.")