import pandas as pd
import matplotlib as plt
import numpy as np

df = pd.read_excel("completed_trades.xlsx")

# Remove trades where VIX is missing
df = df.dropna(subset=["VIX", "gross_pnl"])

plt.figure(figsize=(10, 6))

plt.scatter(
    df["VIX"],
    df["gross_pnl"],
    alpha=0.5
)

plt.xlabel("VIX at Entry")
plt.ylabel("Gross P&L")
plt.title("Gross P&L vs VIX at Entry")

plt.axhline(0, linewidth=1)

plt.show()



x = df["VIX"].to_numpy()
y = df["gross_pnl"].to_numpy()

m, b = np.polyfit(x, y, 1)

plt.figure(figsize=(10, 6))

plt.scatter(x, y, alpha=0.5)
plt.plot(x, m * x + b)

plt.axhline(0, linewidth=1)

plt.xlabel("VIX at Entry")
plt.ylabel("Gross P&L")
plt.title("Gross P&L vs VIX at Entry")

plt.show()

print(f"Correlation: {np.corrcoef(x, y)[0,1]:.3f}")