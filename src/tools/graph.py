import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_excel(r"C:\Users\tbibb\Downloads\completed_trades1.xlsx")

# Remove trades where VIX is missing
df = df.dropna(subset=["VIX", "gross_pnl"])

plt.figure(figsize=(10, 6))

plt.scatter(
    df["VIX"],
    df["gross_pnl"],
    alpha=0.5
)

plt.axhline(0, linewidth=1)

plt.xlabel("VIX at Entry")
plt.ylabel("Gross P&L")
plt.title("Gross P&L vs VIX at Entry")

plt.show()