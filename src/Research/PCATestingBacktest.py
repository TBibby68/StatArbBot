import yfinance as yf
import pandas as pd

# PCA file: goal here is to test the 100 biggest banks currently and then get a basket of 10 to test coint on through PCA, and 
# then testing the PCs for stationarity using the ADF test. We then choose the first stationary PC, and get the top 10 weighted 
# stocks in that vector, and test on that basket.  

# 1) import tickers from excel using pandas:
df = pd.read_excel("banks to trade on.xlsx")
print(df)

#data = yf.download(tickers, start="2010-01-01", end="2024-01-01")['Adj Close']