import alpaca_trade_api as tradeapi
from config import API_KEY, API_SECRET, BASE_URL
# this is the file that handles the trade input to the alpaca API 

# Set up Alpaca REST API connection to the paper trading part of the API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

def place_pair_trade(symbol_a, symbol_b, qty, currentZscore, previousZscore, signal, order_type="market", time_in_force="gtc"):
    """
    Places a pair trade between symbol_a and symbol_b based on z-score and signal.
    If signal is 'OPEN', opens a long/short position based on z direction.
    If signal is 'CLOSE', closes both positions by placing opposing orders.
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

            api.submit_order(symbol=symbol_a, qty=qty, side=side_a, type=order_type, time_in_force=time_in_force)
            api.submit_order(symbol=symbol_b, qty=qty, side=side_b, type=order_type, time_in_force=time_in_force)
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
            # Always close by reversing current positions (assumes symmetrical qty)
            api.submit_order(symbol=symbol_a, qty=qty, side=side_a, type=order_type, time_in_force=time_in_force)
            api.submit_order(symbol=symbol_b, qty=qty, side=side_b, type=order_type, time_in_force=time_in_force)
            print(f"[CLOSE] BUY {qty} {symbol_a} | SELL {qty} {symbol_b}")

    except Exception as e:
        print(f"[ERROR] Failed to place pair trade: {e}")