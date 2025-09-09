from ..config import API_KEY, API_SECRET, BASE_URL, stream_url, engine_string, crypto_stream_url, CRYPTO_API_KEY, CRYPTO_SECRET
import asyncio
import websockets
import json
import numpy as np
from StatArbBot.Backtesting.signals import update_and_get_signal # to get the trading signals
from StatArbBot.Trading.trading import place_pair_trade # to actually do the trading
import StatArbBot.Backtesting.GlobalVariables as GlobalVariables
from sqlalchemy import create_engine # for the 3 months to jump start it
import pandas as pd
from collections import deque

engine = create_engine(engine_string)

# literally just query the db. 
def find_initial_pair(engine):
    df = pd.read_sql('SELECT * FROM live_cointegration_results WHERE p_value < 0.05 ORDER BY p_value LIMIT 1', con=engine)
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

stock1_price = None
stock2_price = None
# price queues for the beta calculations
stock1_prices = deque(maxlen=200)
stock2_prices = deque(maxlen=200)
initial_pair = find_initial_pair(engine)
stock1_ticker = initial_pair[0].iloc[0]
stock2_ticker = initial_pair[1].iloc[0]

# setting up the websocket connection directly here 
async def alpaca_socket():
    global stock1_price  # so we can update it
    global stock2_price
    try:
        async with websockets.connect(stream_url) as ws:
            # Authenticate with the usual details
            auth_msg = {
                "action": "auth",
                "key": API_KEY,
                "secret": API_SECRET
            }
            await ws.send(json.dumps(auth_msg)) # this sends the request to authenticate 

            # Subscribe to bars: the exchange rate from USD to GBP will effect this a little.
            sub_msg = {
                "action": "subscribe",
                "bars": [stock1_ticker, stock2_ticker]
            }
            # we get json responses from the API. 
            await ws.send(json.dumps(sub_msg)) # this pulls the response 

            GlobalVariables.last_signal = None # to track the last order 

            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                # all response messages will be list of dictionaries
                if isinstance(data, list):
                    for item in data:
                        if item.get("T") == "b": # an OHLCV bar message: this is the response we need
                            if item.get("S") == stock1_ticker:
                                stock1_price = item["c"]  # close price of stock 1 
                                stock1_prices.append(stock1_price)
                            elif item.get("S") == stock2_ticker:
                                stock2_price = item["c"] # close price of stock 2
                                stock2_prices.append(stock2_price)

                            if stock2_price is not None and stock1_price is not None and min(len(stock1_prices), len(stock2_prices)) == 200:
                                # need to make sure that we have 200 minutes of rolling history 
                                beta = compute_beta(stock1_prices, stock2_prices)
                                signal = update_and_get_signal(stock1_price, stock2_price, beta) # want this to return the z scores queue as well
                                if signal not in (None, GlobalVariables.last_signal):
                                    value = 10
                                    # need to pull through the current and previous z scores: current is -1 and previous is 0
                                    place_pair_trade(stock1_ticker, stock2_ticker, stock1_price, stock2_price, value, GlobalVariables.z_scores[-1], GlobalVariables.z_scores[0], signal)
                                    GlobalVariables.last_signal = signal
                else:
                    print("Non-bar message:", data)
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"WebSocket failed with HTTP status: {e.status_code}")

asyncio.run(alpaca_socket())
# this seems to be working for getting minute by minute data.