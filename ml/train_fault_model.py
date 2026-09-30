import os, warnings
warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
import mlflow, mlflow.xgboost
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score
import psycopg2

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("atm_fault_prediction")

conn = psycopg2.connect(host="postgres", dbname="atm_warehouse",
                        user="atm", password="atm_pass")
df = pd.read_sql("""SELECT atm_id, event_date, faults, warnings, unresolved,
                           total_downtime_mins, card_reader_events,
                           dispenser_events, printer_events, network_events,
                           display_events, power_unit_events, sensors_events,
                           faults_ma_30d
                    FROM gold.fct_atm_fault_events
                    ORDER BY atm_id, event_date""", conn)
conn.close()

df["fault_tomorrow"] = df.groupby("atm_id")["faults"].shift(-1).fillna(0).astype(int)

feats = ["warnings", "unresolved", "total_downtime_mins",
         "card_reader_events", "dispenser_events", "printer_events",
         "network_events", "display_events", "power_unit_events",
         "sensors_events", "faults_ma_30d"]

X, y = df[feats].fillna(0), df["fault_tomorrow"]
print("Rows:", len(df), "Positives:", int(y.sum()))

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2,
                                       random_state=42, stratify=y)

with mlflow.start_run(run_name="xgboost_fault_v1"):
    params = {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.05}
    mlflow.log_params(params)

    m = XGBClassifier(eval_metric="logloss", random_state=42, **params)
    m.fit(Xtr, ytr)

    proba = m.predict_proba(Xte)[:, 1]
    pred = (proba > 0.5).astype(int)
    auc = float(roc_auc_score(yte, proba))
    f1 = float(f1_score(yte, pred))
    mlflow.log_metrics({"roc_auc": auc, "f1": f1})

    mlflow.xgboost.log_model(m, "model",
                             registered_model_name="atm_fault_xgboost")

    imp = pd.DataFrame({"feature": feats,
                        "importance": m.feature_importances_})
    imp = imp.sort_values("importance", ascending=False)
    imp.to_csv("/tmp/fi.csv", index=False)
    mlflow.log_artifact("/tmp/fi.csv")

print("ROC-AUC:", round(auc, 4))
print("F1     :", round(f1, 4))
