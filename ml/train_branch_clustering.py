import os, warnings
warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
import mlflow, mlflow.sklearn
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import psycopg2

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("atm_branch_utilisation")

conn = psycopg2.connect(host="postgres", dbname="atm_warehouse",
                        user="atm", password="atm_pass")
df = pd.read_sql("""SELECT atm_id, city, region, atm_type,
                           total_tx, failed_tx, failure_rate,
                           avg_withdrawal_mwk, lifetime_faults
                    FROM gold.dim_atm_network""", conn)
conn.close()
print("Loaded", len(df), "ATMs")

feats = ["total_tx", "failed_tx", "failure_rate",
         "avg_withdrawal_mwk", "lifetime_faults"]
X = df[feats].fillna(0)
Xs = StandardScaler().fit_transform(X)

with mlflow.start_run(run_name="kmeans_branch_v1"):
    mlflow.log_params({"n_clusters": 3})
    km = KMeans(n_clusters=3, random_state=42, n_init=10)
    km.fit(Xs)
    sil = float(silhouette_score(Xs, km.labels_))
    mlflow.log_metrics({"silhouette": sil,
                        "inertia": float(km.inertia_),
                        "n_samples": len(df)})
    df["cluster"] = km.labels_
    df.to_csv("/tmp/bc.csv", index=False)
    mlflow.log_artifact("/tmp/bc.csv")
    mlflow.sklearn.log_model(km, "model",
                             registered_model_name="atm_branch_kmeans")

print("Silhouette:", round(sil, 4))
print(df.groupby("cluster").agg(n=("atm_id", "count"),
                                 avg_tx=("total_tx", "mean")).to_string())
