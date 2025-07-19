import pandas as pd

# this file just creates a new postgres table designed to fit the PCA backtesting data in - 100 stocks 

# 1) import tickers from excel using pandas:
df = pd.read_excel("banks to trade on.xlsx")
