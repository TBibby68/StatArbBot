from ..config import API_KEY, API_SECRET, BASE_URL, stream_url, engine_string, crypto_stream_url, CRYPTO_API_KEY, CRYPTO_SECRET
from ib_insync import *
import numpy as np
from StatArbBot.Backtesting.signals import update_and_get_signal # to get the trading signals
from StatArbBot.Trading.trading import place_pair_trade # to actually do the trading
import StatArbBot.Backtesting.GlobalVariables as GlobalVariables
from sqlalchemy import create_engine # for the 3 months to jump start it
import pandas as pd
from collections import deque
import subprocess
from datetime import datetime, timedelta

# to keep track of the last minute we saw: global
last_minute = { 'stock1': None, 'stock2': None }
last_run_minute = None

def main():

    engine = create_engine(engine_string)

    # literally just query the db. 
    def find_initial_pair(engine):
        df = pd.read_sql("""SELECT * FROM more_crypto_live_cointegration_results WHERE p_value < 0.05 AND stock1 != 'minute' AND stock2 != 'minute' ORDER BY p_value LIMIT 1""", con=engine)
        pair = []
        pair.append(df['stock1'])
        pair.append(df['stock2'])
        # these will be treated as series, even though we know they only have one value, so if we try to print them they will 
        # print the meta data as well, like the name, type and length
        return pair
    
        # method to compute the analytical solution for the hedge ratio from a linear regression between the two stocks. 
    # we will use around 200 minute rolling history for this beta as we trade around every 30 minutes. 
    def compute_beta(s1_Prices, s2_Prices):
        cov_matrix = np.cov(s1_Prices, s2_Prices)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1]
        return beta

    # This file handles the streaming of prices from the alpaca API, and then calls the signals file and the trading file to actually
    # perform the trades and calculate when the spread has widened enough to enter a position

    global stock1_price  # so we can update it
    global stock2_price

    GlobalVariables.last_signal = None # to track the last order 

    # check which pairs we can get data for here: Not: USDT, 
    initial_pair = find_initial_pair(engine)
    stock1_ticker = initial_pair[0].iloc[0]
    stock2_ticker = initial_pair[1].iloc[0]

    # price queues for the beta calculations
    stock1_prices = deque(maxlen=200)
    stock2_prices = deque(maxlen=200)

    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)

    # Contract setup
    contract1 = Crypto(stock1_ticker, 'PAXOS', 'USD')
    contract2 = Crypto(stock2_ticker, 'PAXOS', 'USD')

    # Subscribe to 5-second real-time bars for each stock
    bars1 = ib.reqRealTimeBars(contract1, 5, 'TRADES', useRTH=True)
    bars2 = ib.reqRealTimeBars(contract2, 5, 'TRADES', useRTH=True)

    # this is the main function that runs the bot, this is triggered when we get new prices coming in
    def onBarUpdate(bars, hasNewBar, contract):
        global last_run_minute

        if not hasNewBar:
            return

        bar = bars[-1]
        minute_bucket = bar.time.replace(second=0, microsecond=0)

        # Decide which stock this is
        symbol = getattr(contract, 'symbol', 'Unknown')

        if symbol == stock1_ticker:
            if last_minute['stock1'] != minute_bucket:
                stock1_prices.append(bar.close)
                last_minute['stock1'] = minute_bucket
                print(f"[{symbol}] Stored 1-min close {bar.close} at {minute_bucket}")
        elif symbol == stock2_ticker:
            if last_minute['stock2'] != minute_bucket:
                stock2_prices.append(bar.close)
                last_minute['stock2'] = minute_bucket
                print(f"[{symbol}] Stored 1-min close {bar.close} at {minute_bucket}")

        # once both stocks have at least 200 closes, we run the bot
        if (len(stock1_prices) >= 5 and len(stock2_prices) >= 5 and last_run_minute != minute_bucket):

            # Compute hedge ratio / beta
            beta = compute_beta(stock1_prices, stock2_prices)
            print(f"Computed beta: {beta}")
            # making sure this if statement doesn't run mulitple times in the same minute[look into this more]
            last_run_minute = minute_bucket

            # Current prices are just the most recent closes
            stock1_price = stock1_prices[-1]
            stock2_price = stock1_prices[-1]

            # Generate signal (and update z-scores internally)
            signal = update_and_get_signal(stock1_price, stock2_price, beta)

            if signal not in (None, GlobalVariables.last_signal):
                print(f"New signal: {signal}")

                # Example trade size
                value = 10  

                place_pair_trade(
                    stock1_ticker,
                    stock2_ticker,
                    stock1_price,
                    stock2_price,
                    value,
                    GlobalVariables.z_scores[-1],  # most recent z-score
                    GlobalVariables.z_scores[0],   # previous z-score
                    signal
                )

                print("Trade placed!")
                GlobalVariables.last_signal = signal

    # "Inject" the contract when attaching the event handler
    bars1.updateEvent += lambda bars, hasNewBar: onBarUpdate(bars, hasNewBar, contract1)
    bars2.updateEvent += lambda bars, hasNewBar: onBarUpdate(bars, hasNewBar, contract2)


    # Keep connection alive (like your outer while True)
    ib.run()

if __name__ == "__main__":
    main()