import pandas as pd, numpy as np, os

RAW    = "data/raw"
REPORT = "data/reports"
os.makedirs(REPORT, exist_ok=True)

FILES = {
    "ATM master"    : "dim_atm_network.csv",
    "Transactions"  : "fct_atm_transactions.csv",
    "Cash levels"   : "fct_atm_cash_levels.csv",
    "Faults"        : "fct_atm_faults.csv",
    "Replenishments": "fct_replenishments.csv",
    "Weather"       : "weather_lilongwe_2023.csv",
    "Holidays"      : "malawi_holidays_2023.csv",
}

data, lines = {}, []
def log(s=""):
    print(s); lines.append(str(s))

log("=" * 70); log("ATM NETWORK DATA EXPLORATION"); log("=" * 70)

for label, f in FILES.items():
    p = f"{RAW}/{f}"
    if not os.path.exists(p):
        log(f"MISSING: {f}"); continue
    df = pd.read_csv(p)
    data[label] = df
    log(f"\n--- {label} ({f}) ---")
    log(f"  Shape   : {df.shape[0]:,} rows x {df.shape[1]} cols")
    log(f"  Columns : {list(df.columns)}")
    log(f"  Missing : {df.isna().sum().sum():,} nulls")
    num = df.select_dtypes("number")
    if not num.empty:
        log(f"  Numeric :\n{num.describe().T[['mean','std','min','max']].round(1).to_string()}")

if "ATM master" in data:
    a = data["ATM master"]
    log("\n--- ATM coverage by region ---")
    log(a.groupby("region").size().to_string())
    log("\n--- ATM coverage by type ---")
    log(a.groupby("atm_type").size().to_string())

if "Faults" in data:
    f = data["Faults"]
    log("\n--- Fault event breakdown ---")
    log(f.groupby(["event_class","fault_type"]).size().unstack(fill_value=0).to_string())

if "Cash levels" in data:
    c = data["Cash levels"]
    log("\n--- Cash health ---")
    log(f"  Refills               : {int(c['was_refilled'].astype(str).str.lower().eq('true').sum()):,}")
    log(f"  Hours below threshold : {int(c['below_threshold'].astype(str).str.lower().eq('true').sum()):,}")

if "Transactions" in data:
    t = data["Transactions"]
    log("\n--- Transaction breakdown ---")
    log(t.groupby("tx_type").agg(count=("tx_type","count"),
                                 avg_amount=("amount_mwk","mean")).round(0).to_string())
    log(f"\n  Overall success rate : {t['success'].astype(str).str.lower().eq('true').mean()*100:.2f}%")

with open(f"{REPORT}/01_exploration_report.txt","w",encoding="utf8") as fh:
    fh.write("\n".join(lines))
log(f"\nReport saved -> {REPORT}/01_exploration_report.txt")
