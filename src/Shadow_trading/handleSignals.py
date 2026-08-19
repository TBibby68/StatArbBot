from sqlalchemy import text

# helper to test the signal reaction logic

def handle_signal(
    signal,
    z,
    state,
    stock1,
    stock2,
    bar1,
    bar2,
    conn
):
    if signal == "OPEN":

        if state["open_trade"] is None:
            state["open_trade"] = {
                "entry_timestamp": bar1["minute"],
                "stock1": stock1,
                "stock2": stock2,
                "entry_price_1": float(bar1["close"]),
                "entry_price_2": float(bar2["close"]),
                "entry_zscore": float(z),
                "hedge_ratio": float(state["beta"]),
            }

    elif signal == "CLOSE":

        if state["open_trade"] is not None:

            completed_trade = {
                **state["open_trade"],
                "exit_timestamp": bar1["minute"],
                "exit_price_1": float(bar1["close"]),
                "exit_price_2": float(bar2["close"]),
                "exit_zscore": float(z),
            }

            insert_completed_shadow_trade(
                conn,
                completed_trade
            )

            state["open_trade"] = None

# push to the postgres db
def insert_completed_shadow_trade(conn, completed_trade):
    
    cleaned_trade = {
        key: value.item() if hasattr(value, "item") else value
        for key, value in completed_trade.items()
    }
    
    conn.execute(
        text("""
            INSERT INTO shadow_trades (
                entry_timestamp,
                exit_timestamp,
                stock1,
                stock2,
                entry_price_1,
                entry_price_2,
                exit_price_1,
                exit_price_2,
                entry_zscore,
                exit_zscore,
                hedge_ratio
            )
            VALUES (
                :entry_timestamp,
                :exit_timestamp,
                :stock1,
                :stock2,
                :entry_price_1,
                :entry_price_2,
                :exit_price_1,
                :exit_price_2,
                :entry_zscore,
                :exit_zscore,
                :hedge_ratio
            )
        """),
        cleaned_trade
    )