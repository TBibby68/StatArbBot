from ib_insync import *
import time
from sqlalchemy import create_engine, text
from StatArbBot.config import engine_string
from datetime import datetime, timezone
import pandas as pd
from signalGeneration import get_signal
from handleSignals import handle_signal
from hedgeRatio import hedge_ratio
from collections import deque
from execution import execute_pair, reverse_action, insert_completed_shadow_trade

PAPER_MODE = False

# empty as it is edited in the signal function
spread_history = deque(maxlen=100)
open_trade = None

current_bars = {
    "JPM": None,
    "BAC": None,
    "WFC": None,
}

latest_completed_bars = {}

# testing the engingeering with multiple pairs.
pair_states = {
    ("JPM", "BAC"): {
        "beta": 1.0,  # temporary engineering value
        "spread_history": deque(maxlen=100),
        "open_trade": None,
        "last_processed_minute": None,
    },
    ("BAC", "WFC"): {
        "beta": 1.0,
        "spread_history": deque(maxlen=100),
        "open_trade": None,
        "last_processed_minute": None,
    },
    ("JPM", "WFC"): {
        "beta": 1.0,
        "spread_history": deque(maxlen=100),
        "open_trade": None,
        "last_processed_minute": None,
    },
}

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
    wfc = Stock("WFC", "SMART", "USD")

    qualified = ib.qualifyContracts(jpm, bac, wfc)

    contracts = {
        "JPM": jpm,
        "BAC": bac,
        "WFC": wfc,
    }

    print("Qualified contracts:")
    for contract in qualified:
        print(contract)

    jpm_ticker = ib.reqMktData(jpm)
    bac_ticker = ib.reqMktData(bac)
    wfc_ticker = ib.reqMktData(wfc)

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
        "WFC": None
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
                "WFC": wfc_ticker.marketPrice(),
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
                "WFC": {
                    "bid": wfc_ticker.bid,
                    "ask": wfc_ticker.ask,
                    "last": wfc_ticker.last,
                    "mid": wfc_ticker.marketPrice(),
                }
            }

            # engine.begin() automatically commits inserts
            with engine.begin() as conn:

                # iterate through all the stocks present in our pairs
                for ticker in ["JPM", "BAC", "WFC"]:

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

                        # Remember the completed bar
                        latest_completed_bars[ticker] = current_bar

                        # Start new minute bar
                        current_bars[ticker] = create_new_bar(
                            minute,
                            price
                        )
                                
                for (stock1, stock2), state in pair_states.items():

                    bar1 = latest_completed_bars.get(stock1)
                    bar2 = latest_completed_bars.get(stock2)

                    if bar1 is None or bar2 is None:
                        continue

                    if bar1["minute"] != bar2["minute"]:
                        continue

                    completed_minute = bar1["minute"]

                    # IMPORTANT:
                    # Don't process this pair's same minute twice
                    if state["last_processed_minute"] == completed_minute:
                        continue

                    signal, z = get_signal(
                        price_a=bar1["close"],
                        price_b=bar2["close"],
                        open_trade=state["open_trade"],
                        spread_history=state["spread_history"],
                        beta=state["beta"],
                    )

                    # Mark minute as processed
                    state["last_processed_minute"] = completed_minute

                    print(
                        completed_minute,
                        stock1,
                        stock2,
                        "z:",
                        z,
                        "signal:",
                        signal
                    )

                    # either open or close a position depending on the signal
                    if signal == "OPEN" and state["open_trade"] is None:

                        if z > 0:
                            action1 = "SELL"
                            action2 = "BUY"
                        else:
                            action1 = "BUY"
                            action2 = "SELL"

                        if PAPER_MODE:
                            fill1, fill2 = execute_pair(
                                ib=ib,
                                contract1=contracts[stock1],
                                contract2=contracts[stock2],
                                action1=action1,
                                action2=action2,
                                quantity1=1,
                                quantity2=1,
                            )
                        else:
                            # Shadow execution
                            fill1 = bar1["close"]
                            fill2 = bar2["close"]

                        state["open_trade"] = {
                            "entry_timestamp": bar1["minute"],
                            "stock1": stock1,
                            "stock2": stock2,
                            "entry_price_1": fill1,
                            "entry_price_2": fill2,
                            "entry_zscore": float(z),
                            "hedge_ratio": float(state["beta"]),
                            "action1": action1,
                            "action2": action2,
                            "quantity1": 1,
                            "quantity2": 1,
                        }
                    
                    elif signal == "CLOSE" and state["open_trade"] is not None:

                        open_trade = state["open_trade"]

                        if PAPER_MODE:
                            fill1, fill2 = execute_pair(
                                ib=ib,
                                contract1=contracts[stock1],
                                contract2=contracts[stock2],
                                action1=reverse_action(open_trade["action1"]),
                                action2=reverse_action(open_trade["action2"]),
                                quantity1=open_trade["quantity1"],
                                quantity2=open_trade["quantity2"],
                            )
                        else:
                            fill1 = bar1["close"]
                            fill2 = bar2["close"]

                        completed_trade = {
                            **open_trade,
                            "exit_timestamp": bar1["minute"],
                            "exit_price_1": fill1,
                            "exit_price_2": fill2,
                            "exit_zscore": float(z),
                        }

                        insert_completed_shadow_trade(
                            conn=conn,
                            completed_trade=completed_trade
                        )

                        state["open_trade"] = None

                    print(
                        f"{minute} | "
                        f"{stock1}-{stock2} | "
                        f"z={z:.3f} | "
                        f"signal={signal} | "
                        f"open_trade={state['open_trade'] is not None}"
                    )

                    print(
                        stock1,
                        stock2,
                        "history:",
                        len(state["spread_history"])
                    )

                    print(
                        bar1["minute"],
                        stock1,
                        stock2,
                        "z:",
                        z,
                        "signal:",
                        signal
                    )

                ib.sleep(1)

    except KeyboardInterrupt:
        print("Stopping market-data logger...")

    finally:
        ib.disconnect()

if __name__ == "__main__":
    main()