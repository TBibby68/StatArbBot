from ib_insync import *
import time
from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string
from datetime import datetime, timezone
import pandas as pd

# just want to prove we can stream delayed prices into python: need to ensure the writing to postgres works

def insert_market_data(conn, timestamp, ticker, bid, ask, last, mid):
    conn.execute(
        text("""
            INSERT INTO ibkr_market_data
                (timestamp, ticker, bid, ask, last, mid)
            VALUES
                (:timestamp, :ticker, :bid, :ask, :last, :mid)
        """),
        {
            "timestamp": timestamp,
            "ticker": ticker,
            "bid": bid,
            "ask": ask,
            "last": last,
            "mid": mid,
        }
    )

def insert_minute_bar(conn, ticker, bar):

    conn.execute(
        text("""
            INSERT INTO ibkr_minute_bars
                (timestamp, ticker, open, high, low, close)
            VALUES
                (:timestamp, :ticker, :open, :high, :low, :close)
        """),
        {
            "timestamp": bar["minute"],
            "ticker": ticker,
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
        }
    )

def create_new_bar(minute, price):

    return {
        "minute": minute,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
    }

def update_bar(bar, price):

    bar["high"] = max(bar["high"], price)
    bar["low"] = min(bar["low"], price)
    bar["close"] = price

def ts(): return time.strftime("%H:%M:%S")

# to keep track of the last minute we saw
last_minute = { 'stock1': None, 'stock2': None }
last_run_minute = None

def main():

    # --------------------------------------------------------
    # IBKR
    # --------------------------------------------------------

    ib = IB()

    ib.connect(
        "127.0.0.1",
        4001,
        clientId=1
    )

    print("Connected to IBKR:", ib.isConnected())

    # Delayed market data
    ib.reqMarketDataType(3)

    jpm = Stock("JPM", "SMART", "USD")
    bac = Stock("BAC", "SMART", "USD")

    qualified = ib.qualifyContracts(jpm, bac)

    print("Qualified contracts:")
    for contract in qualified:
        print(contract)

    jpm_ticker = ib.reqMktData(jpm)
    bac_ticker = ib.reqMktData(bac)

    # Allow initial market-data fields to populate
    ib.sleep(5)

    # --------------------------------------------------------
    # Postgres
    # --------------------------------------------------------

    engine = create_engine(engine_string)

    print("Connected to Postgres")

    current_bars = {
        "JPM": None,
        "BAC": None,
    }

    try:

        while True:

            timestamp = datetime.now(timezone.utc)

            # Round down to beginning of minute
            minute = timestamp.replace(
                second=0,
                microsecond=0
            )

            prices = {
                "JPM": jpm_ticker.marketPrice(),
                "BAC": bac_ticker.marketPrice(),
            }

            raw_data = {
                "JPM": {
                    "bid": jpm_ticker.bid,
                    "ask": jpm_ticker.ask,
                    "last": jpm_ticker.last,
                    "mid": jpm_ticker.marketPrice(),
                },
                "BAC": {
                    "bid": bac_ticker.bid,
                    "ask": bac_ticker.ask,
                    "last": bac_ticker.last,
                    "mid": bac_ticker.marketPrice(),
                },
            }

            # engine.begin() automatically commits inserts
            with engine.begin() as conn:

                for ticker in ["JPM", "BAC"]:

                    price = prices[ticker]

                    # ------------------------------------------
                    # Save raw ~1-second snapshot
                    # ------------------------------------------

                    insert_market_data(
                        conn=conn,
                        timestamp=timestamp,
                        ticker=ticker,
                        bid=raw_data[ticker]["bid"],
                        ask=raw_data[ticker]["ask"],
                        last=raw_data[ticker]["last"],
                        mid=raw_data[ticker]["mid"],
                    )

                    current_bar = current_bars[ticker]

                    # ------------------------------------------
                    # First observation
                    # ------------------------------------------

                    if current_bar is None:

                        current_bars[ticker] = create_new_bar(
                            minute,
                            price
                        )

                    # ------------------------------------------
                    # Still inside same minute
                    # ------------------------------------------

                    elif current_bar["minute"] == minute:

                        update_bar(
                            current_bar,
                            price
                        )

                    # ------------------------------------------
                    # New minute has begun
                    # ------------------------------------------

                    else:

                        # Save completed previous minute
                        insert_minute_bar(
                            conn=conn,
                            ticker=ticker,
                            bar=current_bar
                        )

                        print(
                            f"Completed {ticker} bar:",
                            current_bar
                        )

                        # Start new minute bar
                        current_bars[ticker] = create_new_bar(
                            minute,
                            price
                        )

                ib.sleep(1)

    except KeyboardInterrupt:
        print("Stopping market-data logger...")

    finally:
        ib.disconnect()

if __name__ == "__main__":
    main()