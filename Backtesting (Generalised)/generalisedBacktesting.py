import numpy as np
from StatArbBot.Backtesting.signals import update_and_get_signal
from StatArbBot.Backtesting import GlobalVariables
import pandas as pd
from StatArbBot.Backtesting.EGinPythonBACKTEST import CointegrationBacktestQuery
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
import importlib.metadata
try:
    from pykalman import KalmanFilter
except importlib.metadata.PackageNotFoundError:
    KalmanFilter = None

