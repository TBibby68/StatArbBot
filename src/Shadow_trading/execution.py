from ib_insync import MarketOrder

def submit_order(
    ib,
    contract,
    action,
    quantity
):
    order = MarketOrder(
        action=action,
        totalQuantity=quantity
    )

    trade = ib.placeOrder(
        contract,
        order
    )

    return trade

# orders are async, so we need to wait for them to actually fill to continue the strategy
def wait_for_fill(ib, trade, timeout_seconds=30):

    elapsed = 0

    while not trade.isDone():

        print(
            "status:",
            trade.orderStatus.status,
            "filled:",
            trade.orderStatus.filled,
            "remaining:",
            trade.orderStatus.remaining,
            "avgFillPrice:",
            trade.orderStatus.avgFillPrice
        )

        ib.sleep(0.5)
        elapsed += 0.5

        if elapsed >= timeout_seconds:
            ib.cancelOrder(trade.order)
            raise TimeoutError(
                f"Order did not fill within {timeout_seconds} seconds"
            )

    if trade.orderStatus.status != "Filled":
        raise RuntimeError(
            f"Order did not fill successfully: "
            f"{trade.orderStatus.status}"
        )

    return float(trade.orderStatus.avgFillPrice)

# opens/closes a position and waits for it to actually be filled
def execute_pair(
    ib,
    contract1,
    contract2,
    action1,
    action2,
    quantity1,
    quantity2
):
    trade1 = submit_order(
        ib=ib,
        contract=contract1,
        action=action1,
        quantity=quantity1
    )

    trade2 = submit_order(
        ib=ib,
        contract=contract2,
        action=action2,
        quantity=quantity2
    )

    fill1 = wait_for_fill(
        ib,
        trade1
    )

    fill2 = wait_for_fill(
        ib,
        trade2
    )

    return fill1, fill2


def reverse_action(action):
    return "SELL" if action == "BUY" else "BUY"