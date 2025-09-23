import alpaca_trade_api as tradeapi
from StatArbBot.config import API_KEY, API_SECRET, BASE_URL
from ib_insync import *
# this is the file that handles the trade input to the alpaca API 

# Set up Alpaca REST API connection to the paper trading part of the API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

def place_pair_trade(symbol_a, symbol_b, symbol_a_price, symbol_b_price, qty, currentZscore, previousZscore, signal, ib):
    """
    Places a pair trade between symbol_a and symbol_b based on z-score and signal.
    If signal is 'OPEN', opens a long/short position based on z direction.
    If signal is 'CLOSE', closes both positions by placing opposing orders.
    it is important to note that qty is the units, not the absolute amount!
    """

    try:
        if signal == "OPEN":
            if currentZscore > 0:
                # z positive: spread is too high → short A, long B
                side_a = "sell" # sell symbol_a
                side_b = "buy" # buy symbol_b
            else:
                # z negative: spread is too low → long A, short B
                side_a = "buy"
                side_b = "sell"

            print(f"[OPEN] {side_a.upper()} {qty} {symbol_a} | {side_b.upper()} {qty} {symbol_b}")

        elif signal == "CLOSE": # close out the current position
            if previousZscore > 0: # we will always have a previous z score to work with as close will never be before an open
                # z positive: spread is too high → short A, long B
                side_a = "buy"
                side_b = "sell"
            else:
                # z negative: spread is too low → long A, short B
                side_a = "sell"
                side_b = "buy"
            
        # Actually place the trades
        print(f"[CLOSE] BUY {qty} {symbol_a} | SELL {qty} {symbol_b}")

        contractA = Crypto(symbol_a, 'PAXOS', 'USD')
        contractB = Crypto(symbol_a, 'PAXOS', 'USD')

        orderA = MarketOrder(side_a, 0)
        orderB = MarketOrder(side_b, 0)

        orderA.cashQty = qty/symbol_a_price
        orderB.cashQty = qty/symbol_b_price

        orderA.tif = 'GTC'
        orderB.tif = 'GTC' 

        # Place order
        ib.placeOrder(contractA, orderA)
        ib.placeOrder(contractB, orderB)

    except Exception as e:
        print(f"[ERROR] Failed to place pair trade: {e}")