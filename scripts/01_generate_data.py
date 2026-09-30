import pandas as pd
import numpy as np
import requests
import os
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
np.random.seed(42)

N_ATMS        = 20
START_DATE    = "2023-01-01"
END_DATE      = "2023-12-31"
STARTING_CASH = 500_000
MIN_CASH      = 50_000
OUTPUT_DIR    = "data/raw"

os.makedirs(OUTPUT_DIR, exist_ok=True)
print("Starting data generation...")

# 1 ATM master
print("Generating ATM master...")
locations = [
    ("Lilongwe",   "Central",  -13.9669,  33.7873),
    ("Blantyre",   "Southern", -15.7861,  35.0058),
    ("Mzuzu",      "Northern", -11.4658,  34.0207),
    ("Zomba",      "Southern", -15.3833,  35.3167),
    ("Kasungu",    "Central",  -13.0333,  33.4833),
    ("Mangochi",   "Southern", -14.4833,  35.2667),
    ("Salima",     "Central",  -13.7833,  34.4500),
    ("Dedza",      "Central",  -14.3667,  34.3333),
    ("Nkhotakota", "Central",  -12.9167,  34.3000),
    ("Liwonde",    "Southern", -15.0667,  35.2333),
]
atm_types  = ["Full-service", "Mini", "Drive-through", "Kiosk"]
atm_models = ["NCR SelfServ 34", "Diebold DN200", "Hyosung MX5600", "Wincor ProCash"]
banks      = ["National Bank of Malawi", "Standard Bank", "FDH Bank", "NBS Bank"]

atms = []
for i in range(1, N_ATMS + 1):
    loc = fake.random_element(locations)
    atms.append({
        "atm_id"        : f"ATM_{i:03d}",
        "city"          : loc[0],
        "region"        : loc[1],
        "latitude"      : loc[2] + np.random.uniform(-0.05, 0.05),
        "longitude"     : loc[3] + np.random.uniform(-0.05, 0.05),
        "atm_type"      : fake.random_element(atm_types),
        "atm_model"     : fake.random_element(atm_models),
        "bank"          : fake.random_element(banks),
        "installed_date": str(fake.date_between("-5y", "-1y")),
        "is_active"     : True,
    })
dim_atm = pd.DataFrame(atms)
dim_atm.to_csv(f"{OUTPUT_DIR}/dim_atm_network.csv", index=False)
print(f"  OK dim_atm_network.csv - {len(dim_atm)} rows")

# 2 Transactions
print("Generating transactions - takes about 2 minutes...")
dates    = pd.date_range(START_DATE, END_DATE, freq="h")
tx_types = ["withdrawal", "balance_enquiry", "deposit", "transfer"]
rows     = []
for atm_id in dim_atm["atm_id"]:
    print(f"    processing {atm_id}...")
    for dt in dates:
        is_weekend   = dt.weekday() >= 5
        is_month_end = dt.day >= 26
        is_peak      = 9 <= dt.hour <= 17
        lam = (12
               * (1.6 if is_weekend   else 1.0)
               * (2.0 if is_month_end else 1.0)
               * (1.4 if is_peak      else 0.4))
        n_tx = np.random.poisson(lam)
        for _ in range(n_tx):
            tx_type = np.random.choice(tx_types, p=[0.65, 0.20, 0.10, 0.05])
            rows.append({
                "atm_id"    : atm_id,
                "timestamp" : dt + timedelta(minutes=int(np.random.randint(0, 59))),
                "tx_type"   : tx_type,
                "amount_mwk": int(np.random.randint(500, 50_000)) if tx_type == "withdrawal" else 0,
                "card_type" : np.random.choice(["Visa","Mastercard","UnionPay","Local"], p=[0.40,0.35,0.05,0.20]),
                "success"   : np.random.choice([True, False], p=[0.97, 0.03]),
            })
fct_tx = pd.DataFrame(rows)
fct_tx.to_csv(f"{OUTPUT_DIR}/fct_atm_transactions.csv", index=False)
print(f"  OK fct_atm_transactions.csv - {len(fct_tx):,} rows")

# 3 Cash levels
print("Generating cash levels...")
cash_rows = []
for atm_id in dim_atm["atm_id"]:
    cash = STARTING_CASH
    for dt in pd.date_range(START_DATE, END_DATE, freq="h"):
        is_weekend   = dt.weekday() >= 5
        is_month_end = dt.day >= 26
        is_peak      = 9 <= dt.hour <= 17
        withdrawal = int(np.random.poisson(
            800
            * (1.5 if is_weekend   else 1.0)
            * (1.8 if is_month_end else 1.0)
            * (1.3 if is_peak      else 0.4)))
        cash     = max(0, cash - withdrawal)
        refilled = False
        if cash < MIN_CASH:
            cash     = STARTING_CASH
            refilled = True
        cash_rows.append({
            "atm_id"               : atm_id,
            "timestamp"            : dt,
            "cash_level_mwk"       : cash,
            "hourly_withdrawal_mwk": withdrawal,
            "was_refilled"         : refilled,
            "below_threshold"      : cash < MIN_CASH,
        })
fct_cash = pd.DataFrame(cash_rows)
fct_cash.to_csv(f"{OUTPUT_DIR}/fct_atm_cash_levels.csv", index=False)
print(f"  OK fct_atm_cash_levels.csv - {len(fct_cash):,} rows")
print(f"     Total refills: {fct_cash['was_refilled'].sum()}")

# 4 Fault events
print("Generating fault events...")
fault_types   = ["card_reader_error","cash_dispenser_jam","receipt_printer_failure","connectivity_loss","screen_fault","power_fluctuation","sensor_error"]
component_map = {"card_reader_error":"card_reader","cash_dispenser_jam":"dispenser","receipt_printer_failure":"printer","connectivity_loss":"network","screen_fault":"display","power_fluctuation":"power_unit","sensor_error":"sensors"}
fault_rows = []
for atm_id in dim_atm["atm_id"]:
    age_factor = np.random.uniform(1.0, 2.5)
    n_faults   = int(np.random.randint(10, 25) * age_factor)
    for _ in range(n_faults):
        fault_type = np.random.choice(fault_types)
        fault_dt   = fake.date_time_between(datetime.strptime(START_DATE, "%Y-%m-%d"), datetime.strptime(END_DATE, "%Y-%m-%d"))
        for offset in range(1, 4):
            fault_rows.append({
                "atm_id"         : atm_id,
                "event_timestamp": fault_dt - timedelta(days=offset),
                "fault_type"     : fault_type,
                "component"      : component_map[fault_type],
                "event_class"    : "warning",
                "duration_mins"  : None,
                "resolved"       : None,
                "fault_occurred" : 1,
            })
        fault_rows.append({
            "atm_id"         : atm_id,
            "event_timestamp": fault_dt,
            "fault_type"     : fault_type,
            "component"      : component_map[fault_type],
            "event_class"    : "fault",
            "duration_mins"  : int(np.random.randint(15, 720)),
            "resolved"       : bool(np.random.choice([True,False], p=[0.88,0.12])),
            "fault_occurred" : 1,
        })
fct_faults = pd.DataFrame(fault_rows).sort_values("event_timestamp")
fct_faults.to_csv(f"{OUTPUT_DIR}/fct_atm_faults.csv", index=False)
print(f"  OK fct_atm_faults.csv - {len(fct_faults):,} rows")

# 5 Replenishments
print("Generating replenishment log...")
refills = fct_cash[fct_cash["was_refilled"]].copy()[["atm_id","timestamp"]]
refills.columns = ["atm_id","refill_timestamp"]
refills["amount_loaded_mwk"] = STARTING_CASH
refills["cit_team"]          = [f"CIT_TEAM_{np.random.randint(1,5):02d}" for _ in range(len(refills))]
refills["downtime_mins"]     = np.random.randint(20, 90, len(refills))
refills.to_csv(f"{OUTPUT_DIR}/fct_replenishments.csv", index=False)
print(f"  OK fct_replenishments.csv - {len(refills):,} rows")

# 6 Weather
print("Fetching weather from Open-Meteo...")
try:
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={"latitude":-13.9669,"longitude":33.7873,"start_date":START_DATE,"end_date":END_DATE,"daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max","timezone":"Africa/Blantyre"},
        timeout=30)
    weather = pd.DataFrame(r.json()["daily"])
    weather.rename(columns={"time":"date"}, inplace=True)
    weather.to_csv(f"{OUTPUT_DIR}/weather_lilongwe_2023.csv", index=False)
    print(f"  OK weather_lilongwe_2023.csv - {len(weather)} days")
except Exception as e:
    print(f"  SKIP weather - {e}")

# 7 Holidays
print("Fetching Malawi holidays...")
try:
    r = requests.get("https://date.nager.at/api/v3/PublicHolidays/2023/MW", timeout=10)
    holidays = pd.DataFrame(r.json())[["date","name","localName"]]
    holidays.to_csv(f"{OUTPUT_DIR}/malawi_holidays_2023.csv", index=False)
    print(f"  OK malawi_holidays_2023.csv - {len(holidays)} holidays")
except Exception as e:
    print(f"  SKIP holidays - {e}")

# Summary
print()
print("=" * 50)
print("DATA GENERATION COMPLETE")
print("=" * 50)
files = {
    "dim_atm_network.csv"      : "ATM master",
    "fct_atm_transactions.csv" : "Transactions",
    "fct_atm_cash_levels.csv"  : "Cash levels",
    "fct_atm_faults.csv"       : "Fault events",
    "fct_replenishments.csv"   : "Replenishments",
    "weather_lilongwe_2023.csv": "Weather",
    "malawi_holidays_2023.csv" : "Holidays",
}
for fname, desc in files.items():
    path = f"{OUTPUT_DIR}/{fname}"
    if os.path.exists(path):
        kb   = os.path.getsize(path) / 1024
        rows = len(pd.read_csv(path))
        print(f"  OK  {desc:<22} {rows:>10,} rows  {kb:>8.0f} KB")
    else:
        print(f"  MISSING - {fname}")
print("=" * 50)
print("Next: python scripts/02_explore_data.py")
