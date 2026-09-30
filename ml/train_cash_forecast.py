import os, warnings
warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
import mlflow, mlflow.prophet
from prophet import Prophet
import psycopg2

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("atm_cash_forecast")
MIN_CASH = 50_000

conn = psycopg2.connect(host="postgres", dbname="atm_warehouse",
                        user="atm", password="atm_pass")
df = pd.read_sql("""SELECT atm_id, event_date AS ds, avg_cash_mwk AS y
                    FROM gold.fct_atm_daily_cash
                    ORDER BY atm_id, event_date""", conn)
conn.close()
df["ds"] = pd.to_datetime(df["ds"])
print("Loaded", len(df), "rows /", df.atm_id.nunique(), "ATMs")

refill = 0
maes = []
for atm_id, grp in df.groupby("atm_id"):
    g = grp[["ds","y"]].sort_values("ds").reset_index(drop=True)
    if len(g) < 30:
        continue
    train, test = g[:-7], g[-7:]
    with mlflow.start_run(run_name=f"prophet_{atm_id}"):
        mlflow.log_params({"atm_id": atm_id, "train_rows": len(train)})
        m = Prophet(daily_seasonality=False, weekly_seasonality=True,
                    yearly_seasonality=True, changepoint_prior_scale=0.05,
                    interval_width=0.80)
        m.fit(train)
        fc = m.predict(test[["ds"]])
        mae = float(np.mean(np.abs(test["y"].values - fc["yhat"].values)))
        mlflow.log_metric("mae", mae)
        mlflow.prophet.log_model(m, "model")
        fut = m.predict(m.make_future_dataframe(periods=3, freq="D")).tail(3)
        nr = bool((fut["yhat_lower"] < MIN_CASH).any())
        mlflow.log_metric("needs_refill_72h", int(nr))
        refill += int(nr)
        maes.append(mae)

print("ATMs needing refill 72h:", refill)
print("Avg MAE:", round(float(np.mean(maes))))
