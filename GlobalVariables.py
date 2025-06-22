from collections import deque
# Global variables file

last_signal = None # self explanatory the last trading signal we had 
z_scores = deque(maxlen=2) # This is the z scores for the trading threshold
startIterationForBacktestingEngine = 0
number_of_signals = 0
# these are for keeping track of the trades. 
stock1_stock = 0
stock2_stock = 0
cash = 0
max_profit = 0
max_drawdown = 0
entry_price_stock1 = 0
entry_price_stock2 = 0

trade_returns = []