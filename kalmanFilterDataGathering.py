from pykalman import KalmanFilter
import numpy as np 

def compute_beta_kalman(stock1_prices, stock2_prices):
    """
    Estimate time-varying hedge ratio between two time series using Kalman filter.

    Returns:
        numpy array of beta estimates (same length as input series)
    """
    # convert the stock price series into arrays(a stack of T (1x1) arrays)
    X = stock1_prices.values.reshape(-1, 1, 1)
    y = stock2_prices.values

    # here we are modelling: y_t = H_t.x_t + e_t,
    # where H is our hedge ratio at time t (just a series of values in a linear regression instead of 1 constant value). 

    kf = KalmanFilter(
        transition_matrices=[1],
        observation_matrices=X,
        initial_state_mean=0,
        initial_state_covariance=1,
        observation_covariance=5**2,
        transition_covariance=0.01
    )
    
    state_means, _ = kf.filter(y)
    beta_estimates = state_means[:, 0]
    # grab the latest hedge ratio to use for the signal generation
    latest_beta = beta_estimates[-1]
    return latest_beta

