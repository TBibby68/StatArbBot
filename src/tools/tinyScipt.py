from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string

TARGET_MINUTE = 55503

engine = create_engine(engine_string)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT minute, timestamp
            FROM backtesting_data_prices
            WHERE minute = :target_minute
        """),
        {"target_minute": TARGET_MINUTE}
    ).fetchone()

if result:
    print(f"Minute: {result.minute}")
    print(f"Timestamp: {result.timestamp}")
else:
    print(f"No data found for minute {TARGET_MINUTE}")