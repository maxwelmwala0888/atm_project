import pandas as pd
import numpy as np
import requests
import os
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
np.random.seed(42)

START_DATE    = "2023-01-01"
END_DATE      = "2023-12-31"
STARTING_CASH = 500_000
OUTPUT_DIR    = "data/raw"

os.makedirs(OUTPUT_DIR, exist_ok=True)

dim_atm  = pd.read_csv(f"{OUTPUT_DIR}/dim_atm_network.csv")
fct_cash = pd.read_csv(f"{OUTPUT_DIR}/fct_atm_cash_levels.csv")

print("Generating fault events...")
fault_types   = ["card_reader_error","cash_dispenser_jam","receipt_printer_failure","connectivity_loss","screen_fault","power_fluctuation","sensor_error"]
component_map = {"card_reader_error":"card_reader","cash_dispenser_jam":"dispenser","receipt_printer_failure":"printer","connectivity_loss":"network","screen_fault":"display","power_fluctuation":"power_unit","sensor_error":"sensors"}

start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
end_dt   = datetime.strptime(END_DATE,   "%Y-%m-%d")

fault_rows = []
for atm_id in dim_atm["atm_id"]:
    age_factor = np.random.uniform(1.0, 2.5)
    n_faults   = int(np.random.randint(10, 25) * age_factor)
    for _ in range(n_faults):
        fault_type = np.random.choice(fault_types)
        fault_dt   = fake.date_time_between(start_dt, end_dt)
        for offset in range(1, 4):
            fault_rows.append({
                "atm_id": atm_id, "event_timestamp": fault_dt - timedelta(days=offset),
                "fault_type": fault_type, "component": component_map[fault_type],
                "event_class": "warning", "duration_mins": None,
                "resolved": None, "fault_occurred": 1,
            })
        fault_rows.append({
            "atm_id": atm_id, "event_timestamp": fault_dt,
            "fault_type": fault_type, "component": component_map[fault_type],
            "event_class": "fault", "duration_mins": int(np.random.randint(15, 720)),
            "resolved": bool(np.random.choice([True,False], p=[0.88,0.12])),
            "fault_occurred": 1,
        })

fct_faults = pd.DataFrame(fault_rows).sort_values("event_timestamp")
fct_faults.to_csv(f"{OUTPUT_DIR}/fct_atm_faults.csv", index=False)
print(f"  OK fct_atm_faults.csv - {len(fct_faults):,} rows")

print("Generating replenishment log...")
refills = fct_cash[fct_cash["was_refilled"].astype(str).str.lower() == "true"].copy()[["atm_id","timestamp"]]
refills.columns = ["atm_id","refill_timestamp"]
refills["amount_loaded_mwk"] = STARTING_CASH
refills["cit_team"]          = [f"CIT_TEAM_{np.random.randint(1,5):02d}" for _ in range(len(refills))]
refills["downtime_mins"]     = np.random.randint(20, 90, len(refills))
refills.to_csv(f"{OUTPUT_DIR}/fct_replenishments.csv", index=False)
print(f"  OK fct_replenishments.csv - {len(refills):,} rows")

print("Fetching weather from Open-Meteo...")
try:
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={"latitude":-13.9669,"longitude":33.7873,"start_date":START_DATE,"end_date":END_DATE,
                "daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
                "timezone":"Africa/Blantyre"},
        timeout=30)
    weather = pd.DataFrame(r.json()["daily"])
    weather.rename(columns={"time":"date"}, inplace=True)
    weather.to_csv(f"{OUTPUT_DIR}/weather_lilongwe_2023.csv", index=False)
    print(f"  OK weather_lilongwe_2023.csv - {len(weather)} days")
except Exception as e:
    print(f"  SKIP weather - {e}")

print("Fetching Malawi holidays...")
try:
    r = requests.get("https://date.nager.at/api/v3/PublicHolidays/2023/MW", timeout=10)
    holidays = pd.DataFrame(r.json())[["date","name","localName"]]
    holidays.to_csv(f"{OUTPUT_DIR}/malawi_holidays_2023.csv", index=False)
    print(f"  OK malawi_holidays_2023.csv - {len(holidays)} holidays")
except Exception as e:
    print(f"  SKIP holidays - {e}")

print()
print("=" * 50)
print("REMAINING DATA COMPLETE")
print("=" * 50)
for fname in ["dim_atm_network.csv","fct_atm_transactions.csv","fct_atm_cash_levels.csv",
              "fct_atm_faults.csv","fct_replenishments.csv","weather_lilongwe_2023.csv",
              "malawi_holidays_2023.csv"]:
    p = f"{OUTPUT_DIR}/{fname}"
    if os.path.exists(p):
        print(f"  OK  {fname:<32} {len(pd.read_csv(p)):>10,} rows")
    else:
        print(f"  MISSING - {fname}")
print("=" * 50)
