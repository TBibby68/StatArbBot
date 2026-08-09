# StatArbBot:

This project is a trading algorithm, written in python, that follows a statistical arbitrage strategy for trading pairs that have a mean reverting spread. 

## Strategy:

The strategy is based on the concept of cointegeration. In short cointegration means that there exists a combination of two time series that is **stationary**. 
A time series is stationary if its mean, variance and autocovariances are time constant. For the purposes of trading, this means that the time series is "mean-reverting",
that is, if the time series is above its mean, then it has a high likelihood of reverting back down to its mean in the near future. 

This property is what underpins our trading strategy. We find two stocks that we think are cointegrated, and we then track this linear combination that is mean-reverting
(we call this the spread), and then we produce trading signals based on how close or far away from the mean the spread is. 

If we call this spread S_t, then we can track the difference between S_t and its mean over time, which will give us the below graph, where µ is the mean of S_t. If the spread goes beyond
the point µ_1 then we will buy the spread(open a position) wherein we will short one stock and long the other. If the spread then goes back undr µ_0, then we will close out the current 
open position, that is, long the stock we previously shorted, and sell off the stock we previosuly went long on. Cointegration of the two stocks is essential for this behaviour to 
exist, and thus essential for our strategy to work. 

![image](https://github.com/user-attachments/assets/8d7a34e8-793a-402f-b5b1-e6636261ed81)

The baseline works on a rolling 2 week window, meaning that we test the previous 3 months of data for this cointgration relationship, and then if we find that a pair has this relationship, we trade on that pair for the next 2 weeks, at which point
we then recalculate the cointegration, and if the relationship has broken down, we close out the current position if one is open, and we try to find another pair to trade for the next 2 weeks. 

## Assumptions:

The key assumptions of this strategy (which are not very realistic) are that we are trading in a perfectly liquid market, with effectively infinite volumes, meaning that there is no risk posed by reductions in liquidity and thus inability to close positions, and there is also negligable spread. We also assume zero impact on the market from our trades (which at the level we are trading is relatively realisitc). 

The purpose of this project is to investigate the statistical models that can produce a successful alpha generating strategy - implementing this in real life is another step.

## Reproduce these results and investigate yourself:

To run the backtest locally, you will need to set up the postgres db, and link to the Alpaca API, and then run the following files in this order: priceDataCapture.py -> cointegrationDataGathering.py -> backtesting.py (in the backtesting folder). Specific config for the backtest can be edited in the backtestConfig.py file. You can then run the writeDataToExcel.py file to see a complete log of all the trades in the desired period for easy manipulation. 
