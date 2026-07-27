from ib_insync import *
import threading, time, traceback, sys
from decimal import Decimal
# this is the file that handles the trade input to IBKR

def round_lot(qty, lot=Decimal("0.000001")):
    # floor to the allowed increment (example: 6 dp)
    return (Decimal(qty) // lot) * lot

def ts(): return time.strftime("%H:%M:%S")

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

            # first we need to update the results list
            GlobalVariables.experimentResults.append({

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

        # Group the orders so that if one fails, they both fail, 
        # and make sure they both go through at the same time. 

        # have to go through the whole order "lifecycle" for each leg: first leg A
        contractA = Stock(symbol_a, 'SMART', 'USD')
        contractA = ib.qualifyContracts(contractA)[0]
        orderA = MarketOrder(side_a, 10)
        ib.placeOrder(contractA, orderA)

        # then leg B
        contractB = Stock(symbol_b, 'SMART', 'USD')
        contractB = ib.qualifyContracts(contractB)[0]
        orderB = MarketOrder(side_b, 10)
        ib.placeOrder(contractB, orderB)
    except Exception as e:
        print(f"[ERROR] Failed to place pair trade: {e}")