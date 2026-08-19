from datetime import datetime, timezone
from Shadow_trading.handleSignals import handle_signal
from sqlalchemy import create_engine
from StatArbBot.config import engine_string
import pandas as pd

state = {
    "beta": 1.0,
    "open_trade": None
}

bar1 = {
    "minute": datetime.now(timezone.utc),
    "close": 360.0
}

bar2 = {
    "minute": datetime.now(timezone.utc),
    "close": 64.0
}

engine = create_engine(engine_string)

with engine.begin() as conn:

    handle_signal(
        signal="OPEN",
        z=4.0,
        state=state,
        stock1="JPM",
        stock2="BAC",
        bar1=bar1,
        bar2=bar2,
        conn=conn
    )

    handle_signal(
        signal="CLOSE",
        z=0.1,
        state=state,
        stock1="JPM",
        stock2="BAC",
        bar1=bar1,
        bar2=bar2,
        conn=conn
    )

    # count rows before second CLOSE
    before = pd.read_sql(
        "SELECT COUNT(*) AS n FROM shadow_trades",
        con=engine
    )["n"].iloc[0]

    handle_signal(
        signal="CLOSE",
        z=0.1,
        state=state,
        stock1="JPM",
        stock2="BAC",
        bar1=bar1,
        bar2=bar2,
        conn=conn
    )

    after = pd.read_sql(
        "SELECT COUNT(*) AS n FROM shadow_trades",
        con=engine
    )["n"].iloc[0]

    assert after == before

    assert state["open_trade"] is None

    print("CLOSE while flat correctly ignored")