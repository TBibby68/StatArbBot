import numpy as np
# this should be calculated at the end of every trading window to set up the next trading window.

def hedge_ratio(stock1_prices, stock2_prices):

    cov_matrix = np.cov(stock1_prices, stock2_prices)
    ratio = cov_matrix[0, 1] / cov_matrix[1, 1]

    return ratio