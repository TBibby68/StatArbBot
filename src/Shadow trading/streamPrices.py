from ib_insync import *
import time
from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string
from datetime import datetime, timezone

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

    # engine.begin() automatically commits inserts
    with engine.begin() as conn:

        try:

            while True:

                timestamp = datetime.now(timezone.utc)

                # JPM
                insert_market_data(
                    conn=conn,
                    timestamp=timestamp,
                    ticker="JPM",
                    bid=jpm_ticker.bid,
                    ask=jpm_ticker.ask,
                    last=jpm_ticker.last,
                    mid=jpm_ticker.marketPrice(),
                )

                # BAC
                insert_market_data(
                    conn=conn,
                    timestamp=timestamp,
                    ticker="BAC",
                    bid=bac_ticker.bid,
                    ask=bac_ticker.ask,
                    last=bac_ticker.last,
                    mid=bac_ticker.marketPrice(),
                )

                print(
                    timestamp,
                    "JPM:",
                    jpm_ticker.marketPrice(),
                    "| BAC:",
                    bac_ticker.marketPrice()
                )

                ib.sleep(1)

        except KeyboardInterrupt:
            print("Stopping market-data logger...")

        finally:
            ib.disconnect()

if __name__ == "__main__":
    main()