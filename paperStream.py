from config import API_KEY, API_SECRET, BASE_URL, stream_url, crypto_stream_url, CRYPTO_API_KEY, CRYPTO_SECRET
import asyncio
import websockets
import json
import numpy as np
from signals import update_and_get_signal # to get the trading signals
from trading import place_pair_trade # to actually do the trading
import GlobalVariables

# NOTE: keep this file for normal stocks only, and then we can have a separate file for crypto

# method to compute the analytical solution for the hedge ratio from a linear regression between the two stocks. 
# we will use around 200 minute rolling history for this beta as we trade around every 30 minutes. 
def compute_beta(aapl_prices, msft_prices):
    cov_matrix = np.cov(aapl_prices, msft_prices)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1]  
    return beta

# This file handles the streaming of prices from the alpaca API, and then calls the signals file and the trading file to actually
# perform the trades and calculate when the spread has widened enough to enter a position

aapl_price = None

# setting up the websocket connection directly here 
async def alpaca_socket():
    global aapl_price  # so we can update it
    global msft_price
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
                "bars": ["AAPL", "MSFT"]
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
                            if item.get("S") == 'AAPL':
                                aapl_price = item["c"]  # close price of apple
                                print("this is appl price " + str(aapl_price))
                            elif item.get("S") == 'MSFT':
                                msft_price = item["c"] # close price of microsoft
                                print("this is msft price " + str(msft_price))
                
                            if msft_price is not None and aapl_price is not None:
                                #beta = compute_beta(aapl_prices, msft_prices)
                                signal = update_and_get_signal(aapl_price, msft_price, 1) # want this to return the z scores queue as well
                                if signal not in (None, GlobalVariables.last_signal):
                                    # need to pull through the current and previous z scores: current is -1 and previous is 0
                                    place_pair_trade("AAPL", "MSFT", 10, GlobalVariables.z_scores[-1], GlobalVariables.z_scores[0], signal)
                                    GlobalVariables.last_signal = signal
                else:
                    print("Non-bar message:", data)
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"WebSocket failed with HTTP status: {e.status_code}")

asyncio.run(alpaca_socket())
# this seems to be working for getting minute by minute data