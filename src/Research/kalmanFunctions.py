import importlib.metadata
import numpy as np
try:
    from pykalman import KalmanFilter
except importlib.metadata.PackageNotFoundError:
    KalmanFilter = None

def update_kalman_beta(prev_beta, prev_cov, x_new, y_new, kf):
    """
    Update the Kalman filter for one new observation.
    
    Parameters
    ----------
    prev_beta : float
        Previous beta estimate.
    prev_cov : ndarray
        Previous state covariance matrix (1x1 matrix).
    x_new : float
        New stock1 price (the independent variable).
    y_new : float
        New stock2 price (the dependent variable). 
    kf : KalmanFilter
        A configured pykalman KalmanFilter object.
        
    Returns
    -------
    new_beta : float
        Updated beta estimate.
    new_cov : ndarray
        Updated state covariance matrix.
    """
    # reshape x_new into the required (1,1) observation matrix
    obs_matrix = np.array([[x_new]])

    # run one-step Kalman update
    new_state_mean, new_state_cov = kf.filter_update(
        filtered_state_mean = np.array([prev_beta]),
        filtered_state_covariance = prev_cov,
        observation = y_new,
        observation_matrix = obs_matrix
    )

    new_beta = new_state_mean[0]
    return new_beta, new_state_cov

def compute_beta_kalman_initial(stock1_prices, stock2_prices):
    """
    Estimate time-varying hedge ratio between two time series using Kalman filter.

    Returns:
        1) numpy array of beta estimates (same length as input series)
        2) covariance matrix so we can calculate the next beta iteratively
        3) the Kalman filter object
    """
    # convert the stock price series into arrays(a stack of T (1x1) arrays)
    X = stock1_prices.values.reshape(-1, 1, 1)
    y = stock2_prices.values

    # here we are modelling: y_t = H_t.x_t + e_t,
    # where H is our hedge ratio at time t (just a series of values in a linear regression instead of 1 constant value). 
    # the strategy for lower latency is to calculate this initially, but then only increment it every time step after that, so we don't
    # calculate the full 2 weeks of data every minute. The Kalman filter calculates based on the previos beta 

    kf = KalmanFilter(
        transition_matrices=[1],
        observation_matrices=X,
        initial_state_mean=0,
        initial_state_covariance=0.01,
        observation_covariance=25, # high = 25 / low <= 1 => less sensitive to volatility as it assumes more noise
        transition_covariance=0.01 # high = 0.1 => more sensitive to changes over time 
    )

    # for a string covariance relationship, we typically want the transition covariance to be low, observation to be high(but noisy data means a little higher), 
    # transition matrix to be 1, 0 initial state mean, initial state covariance small.
    
    state_means, state_covs = kf.filter(y)
    # gt the latest covariance matrix
    latest_covariance = state_covs[-1]
    beta_estimates = state_means[:, 0]
    # grab the latest hedge ratio to use for the signal generation
    latest_beta = beta_estimates[-1]
    print("this is the latest beta: ", latest_beta)
    return latest_beta, latest_covariance, kf
