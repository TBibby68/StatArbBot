from execution import execute_pair
from ib_insync import *

ib = IB()

ib.connect(
    "127.0.0.1",
    4001,
    clientId=1
)

jpm = Stock("JPM", "SMART", "USD")
bac = Stock("BAC", "SMART", "USD")

ib.qualifyContracts(jpm, bac)

# Allow initial market-data fields to populate
ib.sleep(5)

fill1, fill2 = execute_pair(
    ib=ib,
    contract1=jpm,
    contract2=bac,
    action1="BUY",
    action2="SELL",
    quantity1=1,
    quantity2=1,
)

print("JPM fill:", fill1)
print("BAC fill:", fill2)