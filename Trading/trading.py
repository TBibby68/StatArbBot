from ib_insync import *
import threading, time, traceback, sys
# this is the file that handles the trade input to IBKR

def ts(): return time.strftime("%H:%M:%S")

# NEED TO FIX THIS
def place_pair_trade(symbol_a, symbol_b, cashPrice, currentZscore, previousZscore, signal, ib):
    """
    Places a pair trade between symbol_a and symbol_b based on z-score and signal.
    If signal is 'OPEN', opens a long/short position based on z direction.
    If signal is 'CLOSE', closes both positions by placing opposing orders.
    it is important to note that qty is the units, not the absolute amount!
    """
    print("[ENTER place_pair_trade]", flush=True)

    # debugging to checkl the threading situation
    try:
        msg = f"[{ts()}][{threading.current_thread().name}] ENTER place_pair_trade sig={signal}"
        print(msg, flush=True)
    except Exception as e:
        print("[LOG FORMAT ERROR]", repr(e), flush=True)
        traceback.print_exc(file=sys.stdout)
    assert signal in ("OPEN","CLOSE")
    assert cashPrice is not None


    try:
        if signal == "OPEN":
            if currentZscore > 0:
                # z positive: spread is too high → short A, long B
                side_a = "SELL" # sell symbol_a
                side_b = "BUY" # buy symbol_b
            else:
                # z negative: spread is too low → long A, short B
                side_a = "BUY"
                side_b = "SELL"

            print(f"[OPEN] {side_a.upper()} {cashPrice} {symbol_a} | {side_b.upper()} {cashPrice} {symbol_b}")

        elif signal == "CLOSE": # close out the current position
            if previousZscore > 0: # we will always have a previous z score to work with as close will never be before an open
                # z positive: spread is too high → short A, long B
                side_a = "BUY"
                side_b = "SELL"
            else:
                # z negative: spread is too low → long A, short B
                side_a = "SELL"
                side_b = "BUY"
            
        # Actually place the trades
        print(f"[CLOSE] BUY {cashPrice} {symbol_a} | SELL {cashPrice} {symbol_b}")

        contractA = Crypto(symbol_a, 'PAXOS', 'USD')
        contractB = Crypto(symbol_b, 'PAXOS', 'USD')

        orderA = MarketOrder(side_a, 0)
        orderB = MarketOrder(side_b, 0)

        orderA.cashQty = cashPrice
        orderB.cashQty = cashPrice

        orderA.tif = 'GTC'
        orderB.tif = 'GTC' 

        # Place order with debugging statements 
        print(f"[{ts()}] Pre-IB placeOrder", flush=True)
        ib.placeOrder(contractA, orderA)
        ib.placeOrder(contractB, orderB)
        print(f"[{ts()}] Post-IB placeOrder", flush=True)

    except Exception as e:
        print(f"[ERROR] Failed to place pair trade: {e}")