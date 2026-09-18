import pandas as pd

for fname in ["PlayerStatistics.csv", "PlayerStatisticsExtended.csv"]:
    path = f"data/515/{fname}"
    print(f"\n=== {fname} ===")
    sample = pd.read_csv(path, nrows=5)
    print("Columns:", list(sample.columns))
    print(sample.head(3).to_string())

# Check how current PlayerStatistics.csv actually is (full read is fine, ~389MB, may take ~10-30s)
df = pd.read_csv("data/515/PlayerStatistics.csv")
print("\nTotal rows:", len(df))
date_col = [c for c in df.columns if "date" in c.lower() or "season" in c.lower()]
print("Date/season-like columns:", date_col)
for c in date_col:
    print(f"{c}: min={df[c].min()}, max={df[c].max()}")