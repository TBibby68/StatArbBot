Statistical Arbitrage Research — Cointegration-Based Pairs Trading

1. Project Overview

This project investigates the conditions under which a cointegration-based pairs trading strategy (Equities) can generate persistent returns after transaction costs. Using minute-level US equity data, I construct a rolling research and backtesting framework based on Engle-Granger cointegration and OLS-estimated hedge ratios. Initial experiments showed that apparent gross profitability is highly sensitive to execution costs, signal thresholds and market regime. The subsequent research therefore focuses on identifying when the signal survives realistic costs and whether those relationships persist out-of-sample.

2. Strategy Design

**Pair formation:** At each formation window, test candidate equity pairs (from a manually chosen basket of highly liquid stocks in the same sector) for cointegration using Engle-Granger. For qualifying pairs, estimate the hedge ratio using OLS and construct the spread:

$$
S_t = P_{A,t} - \beta P_{B,t}
$$

**Signal generation:** Standardise the spread using its estimated mean and standard deviation:

$$
z_t = \frac{S_t - \mu_S}{\sigma_S}
$$

Enter when $\(|z_t|\)$ exceeds the entry threshold, taking opposing positions in the two securities according to the estimated hedge ratio. Exit when the spread mean-reverts and $\(|z_t|\)$ falls below the exit threshold.

**Rolling implementation:** Cointegration relationships and hedge ratios are re-estimated on a rolling basis using historical formation windows, followed by separate trading windows (currently 3 month formation window and 2 week trading window). Only information available at the time of each trading decision is used to avoid look ahead bias.

3. Key Results

The research developed iteratively from a simple baseline. While the initial strategy exhibited positive gross performance, introducing realistic execution-cost assumptions completely destroyed any profitability the strategy supposedly had. The original strategy had a high number of weakly profitable trades, and so was very sensitive to transaction costs and slippage. The first experiment conducted was to move the entry threshold further away, with the aim to reduce turnover and increase the average PnL magnitude of trades. This experiment did exactly that, decreasing the gross PnL but increasing the net PnL back to being positive in the backtest period.

The next stage of the research was estimating the return on capital. The initial strategy assumed frictionless short selling, which is not realistic. After estimating the minimum margin requirements of the strategy by tracking the MTM PnL in the backtest, it was apparent that despite the fact that most trades were winning and the strategy was making money, it required such a large amount of capital to run, that the ROC was very small. This motivated the idea of trading CFDs instead of cash equities. Since CFDs are "automatically leveraged" estimations of ROC increased significantly, and made the strategy look viable again. The practical drawback of this change is that to avoid the assumed minimum CFD commissions, the trade size must be relatively (to a retail trader like myself) large. 

The next stage of the research was looking at trade timing. Trades tend to cluster around the market open, so much so that around 2/3 rds of the PnL can be attributed to trades that were opened within the first 5 minutes of the market opening. This is an ongoing area of research for this project, with the main question being: is this clustering due to data issues (unrealistic fill prices, optimistic slippage assumptions, bad data etc), and thus can we trust the validity of these results? If these results are to be trusted, then there might be a "quantitatively cheap" way of improving the PnL of the strategy significantly. That would be to trade on the US markets for the first hour that they are open, and then redeploy capital in Europe when those exchanges open, and then repeat in Asia when they open. This strategy could work because the majority of profit is earned in the first hour of trading, but the other 23 hours of the day the capital is sitting idle. No testing on this modification has been done, and will not be done before live deployment of the baseline either confirms or denies the previous concerns around data, however. 

The next research questions that have to be answered before deploying the strategy live are around the operational side. Primarily if one side of a trade is rejected, but the other side goes through, then we are taking an unmodelled directional position in the market, which is not something the strategy accounts for. The initial idea to handle this is to unravel these trades with a certain time threshold, and accept the loss as a part of the execution costs. This is not something that is currently modelled at all by the strategy, and may make the execution costs higher than assumed. 

The research also turned up some dead ends - hypotheses about how to improve the strategy that ended up not living up to statistical scrutiny. One of these that is particularly interesting is the question around market regimes. The strategy has period where it performs very well, and it has periods where it performs badly. It even has sharp inflection points, such as around th28 February 2026 - before this the strategy was losing money, and then after this up to the end of the backtest the strategy made a lot of money. An initial hypothesis was the volatility caused by the Iran war, which started at this inflection point, but upon running bootstrap tests looking at both VIX and spread volatility, the data seem to suggest that this was not the driving factor of increased returns.

An important note to make is that this project currently lacks any OOS testing, and only has a backtest. Initially the backtest was on the period August 2022 - August 2025, and an OOS test from August 2025 - August 2026 was included. I then used the OOS dataset to further investigate the strategy, so this dataset stopped being OOS, and I have now included it in the backtest dataset.

Currently, I aim to deploy a small amount of capital to this strategy to test whether my assumptions are realistic, and if so, there are some more research questions that need answering before I can scale the strategy in any meaningful way. These are summarised below

"why do trades that are held longer than average have significantly worse PnL"? An idea would be to impose a cut off for positions, beyond which we close them out, and then wait for another entry signal. 

"Does homogeneity of baskets of stocks effect returns"? I ran the strategy on Bank stocks, Tech stocks and Energy stocks, and noticed that energy stocks perform the best, and tech stocks the worst. A hypothesis is that energy stocks are much more homogeneous, because they all share the same underlying price factors: energy price, whereas 2 tech companies can have radically different business models, but be categorised both as "tech" - think Apple, Amamzon, Broadcomm (consumer hardware, Cloud computing, Telecoms). I have some ideas around measuring homogeneity using hyperbolic distance between stocks, but this is something that is a lot more complex than other questions, and may turn out to be a research dead end so is shelved as a question for the future currently. 

"Can we deploy the capital in another strategy while the current stat arb one isn't trading"? This connects to the question around global exchange rotations, and is something that could be as simple as putting the money in Bonds to give us an extra few percentage points of ROC, or it could include running an uncorrelated strategy which takes advantage of mean reversion not being particularly profitable while it is trading (possibly a momentum based strategy). 

"Can we detect when we are in a good market regime for this strategy"? This is potentially the biggest unanswered question, and simultaneously likely the hardest to answer. Currently I think the Iran war somehow made the strategy more profitable, but I have no mechanism to explain why that would be the case. 
