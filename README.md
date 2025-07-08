# StatArbBot:

This project is a trading algorithm, written in python, that follows a statistical arbitrage strategy for trading pairs that have a mean reverting spread. 

## Strategy:

The strategy of this bot is based on the concept of cointegeration. In short cointegration means that there exists a combination of two time series that is **stationary**. 
A time series is stationary if its mean, variance and autocovariances are time constant. For the purposes of trading, this means that the time series is "mean-reverting",
that is, if the time series is above its mean, then it has a high likelihood of reverting back down to its mean in the near future. 

This property is what underpins our trading strategy. We find two stocks that we think are cointegrated, and we then track this linear combination that is mean-reverting
(we call this the spread), and then we produce trading signals based on how close or far away from the mean the spread is. 

If we call this spread S_t, then we can track the difference between S_t and its mean over time, which will give us the below graph, where µ is the mean of S_t. If the spread goes beyond
the point µ_1 then we will buy the spread(open a position) wherein we will short one stock and long the other. If the spread then goes back undr µ_0, then we will close out the current 
open position, that is, long the stock we previously shorted, and sell off the stock we previosuly went long on. Cointegration of the two stocks is essential for this behaviour to 
exist, and thus essential for our strategy to work. 

![image](https://github.com/user-attachments/assets/8d7a34e8-793a-402f-b5b1-e6636261ed81)

The bot works on a rolling 2 week window, meaning that we test the previous 3 months of data for this cointgration relationship, and then if we find that a pair has this relationship, we trade on that pair for the next 2 weeks, at which point
we then recalculate the cointegration, and if the relationship has broken down, we close out the current position if one is open, and we try to find another pair to trade for the next 2 weeks. 

## Assumptions:

The key assumptions of this strategy (which are not very realistic) are that we are trading in a perfectly liquid market, with effectively infinite volumes, meaning that there is no risk posed by reductions in liquidity and thus inability to close positions, and there is also negligable spread. We also assume zero slippage, and then zero impact on the market from our trades. Essentially this is the "perfect" set of conditions for a trading strategy. 

## Kalman filters:



## Project Structure:

This project is a work in progress, and currently the focus is on refining the strategy in backtests so that it has a sharpe ratio estimate of above 0.5. Because of this, the most 
developed and worked on file is **backtesting.py**. Other files that the backtest relies on are **cointegrationDataGathering.py**, **EGinPythonBACKTEST.py**, **priceDataCapture.py**, **signals.py**, and **GlobalVariables.py**. These files 
fetch minute by minute price data for 10 stocks: 10 large US banks(under the qialitative assumption that these stocks are likely to be cointegrated) from the alpaca market API, and then run the **Engle-Granger cointegration hypothesis test**
on each pair of stocks, and then stores the results in several tables in a local postgres database, which we then query when running the backtest simulation.

## Further Development Ideas:

Currently I am working on tracking the performance of each pair. Certain pairs make more money than others despite having the same cointegration test results, which could be an indication of a more reliable relationship existing, 
and so my goal now is to measure this over a longer period(1-2 years instead of 3 months), and analyse the results to possibly give scores to each possible pairing that is combined with the 
cointegration test results to determine which pairs are actually traded. 
