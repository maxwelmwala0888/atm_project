import os, json, uuid
from datetime import datetime
import pandas as pd
import psycopg2

OUT = "/alerts/outbox"
MIN_CASH = 100_000
NOW = datetime.utcnow()

for sub in ("sms", "email", "feed"):
    os.makedirs(f"{OUT}/{sub}", exist_ok=True)

def db():
    return psycopg2.connect(host="postgres", dbname="atm_warehouse",
                            user="atm", password="atm_pass")

def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)

def cash_alerts():
    conn = db()
    df = pd.read_sql("""
        SELECT d.atm_id, d.event_date, d.min_cash_mwk, d.cash_status,
               n.city, n.region
        FROM gold.fct_atm_daily_cash d
        JOIN gold.dim_atm_network n USING (atm_id)
        WHERE d.event_date = (SELECT MAX(event_date) FROM gold.fct_atm_daily_cash)
    """, conn)
    conn.close()

    alerts = []
    for _, r in df.iterrows():
        if r["min_cash_mwk"] >= MIN_CASH:
            continue
        priority = "P1" if r["min_cash_mwk"] < MIN_CASH / 2 else "P2"
        alerts.append({
            "alert_id": str(uuid.uuid4())[:8],
            "type": "cash_refill",
            "created_at": NOW.isoformat(),
            "atm_id": r["atm_id"],
            "city": r["city"],
            "region": r["region"],
            "min_cash_mwk": int(r["min_cash_mwk"]),
            "cash_status": r["cash_status"],
            "priority": priority,
            "sms": (f"[{priority}] ATM {r['atm_id']} ({r['city']}) "
                    f"cash low: {int(r['min_cash_mwk']):,} MWK. "
                    f"Refill needed within 24h."),
            "email_subject": f"[{priority}] Cash refill required: {r['atm_id']}",
            "email_body": (f"ATM {r['atm_id']} in {r['city']} "
                           f"({r['region']}) dropped below minimum.\n"
                           f"Current: {int(r['min_cash_mwk']):,} MWK\n"
                           f"Status: {r['cash_status']}"),
        })
    return alerts

def fault_alerts():
    conn = db()
    df = pd.read_sql("""
        SELECT f.atm_id, f.event_date, f.faults, f.warnings, f.severity,
               f.faults_ma_30d, f.card_reader_events, f.dispenser_events,
               f.printer_events, f.network_events,
               n.city, n.region, n.atm_model
        FROM gold.fct_atm_fault_events f
        JOIN gold.dim_atm_network n USING (atm_id)
        WHERE f.event_date >= (SELECT MAX(event_date) - INTERVAL '30 days'
                               FROM gold.fct_atm_fault_events)
          AND (f.faults > 0 OR f.warnings >= 3)
    """, conn)
    conn.close()

    alerts = []
    for _, r in df.iterrows():
        priority = "P1" if r["severity"] == "high" else ("P2" if r["severity"] == "medium" else "P3")
        parts = []
        for comp, cnt in [("card_reader", r["card_reader_events"]),
                          ("dispenser", r["dispenser_events"]),
                          ("printer", r["printer_events"]),
                          ("network", r["network_events"])]:
            if cnt and cnt > 0:
                parts.append(f"{comp}:{int(cnt)}")
        comps = ", ".join(parts) if parts else "no component data"

        alerts.append({
            "alert_id": str(uuid.uuid4())[:8],
            "type": "fault_prediction",
            "created_at": NOW.isoformat(),
            "atm_id": r["atm_id"],
            "city": r["city"],
            "region": r["region"],
            "atm_model": r["atm_model"],
            "event_date": str(r["event_date"]),
            "severity": r["severity"],
            "faults": int(r["faults"]),
            "warnings": int(r["warnings"]),
            "faults_ma_30d": float(r["faults_ma_30d"]),
            "priority": priority,
            "sms": (f"[{priority}] ATM {r['atm_id']} ({r['city']}) "
                    f"{r['severity']} fault risk. Components: {comps}. "
                    f"Dispatch engineer within 48h."),
            "email_subject": f"[{priority}] Fault risk: {r['atm_id']}",
            "email_body": (f"ATM {r['atm_id']} in {r['city']} ({r['region']})\n"
                           f"Model: {r['atm_model']}\n"
                           f"Severity: {r['severity']}\n"
                           f"Faults: {int(r['faults'])} Warnings: {int(r['warnings'])}\n"
                           f"Components: {comps}"),
        })
    return alerts

def dispatch(alerts):
    feed = []
    for a in alerts:
        aid = f"{a['type']}_{a['atm_id']}_{a['alert_id']}"

        write_json(f"{OUT}/sms/{aid}.json", {
            "to": "CIT_TEAM" if a["type"] == "cash_refill" else "FIELD_ENGINEER",
            "from": "ATM_OPS",
            "priority": a["priority"],
            "body": a["sms"],
            "sent_at": a["created_at"],
            "atm_id": a["atm_id"],
        })

        write_json(f"{OUT}/email/{aid}.json", {
            "to": "ops@bank.example",
            "subject": a["email_subject"],
            "body": a["email_body"],
            "priority": a["priority"],
            "sent_at": a["created_at"],
            "atm_id": a["atm_id"],
        })

        feed.append({
            "alert_id": a["alert_id"],
            "type": a["type"],
            "priority": a["priority"],
            "atm_id": a["atm_id"],
            "city": a["city"],
            "message": a["sms"],
            "created_at": a["created_at"],
        })

    write_json(f"{OUT}/feed/latest.json", {
        "generated_at": NOW.isoformat(),
        "total_alerts": len(feed),
        "by_type": {
            "cash_refill": sum(1 for f in feed if f["type"] == "cash_refill"),
            "fault_prediction": sum(1 for f in feed if f["type"] == "fault_prediction"),
        },
        "by_priority": {
            "P1": sum(1 for f in feed if f["priority"] == "P1"),
            "P2": sum(1 for f in feed if f["priority"] == "P2"),
            "P3": sum(1 for f in feed if f["priority"] == "P3"),
        },
        "alerts": feed,
    })

def main():
    print("Generating alerts...")
    cash = cash_alerts()
    fault = fault_alerts()
    all_a = cash + fault
    print(f"  Cash alerts : {len(cash)}")
    print(f"  Fault alerts: {len(fault)}")
    print(f"  Total       : {len(all_a)}")

    dispatch(all_a)
    print(f"\nWritten to {OUT}/")
    print(f"  sms/   -> {len(all_a)} files")
    print(f"  email/ -> {len(all_a)} files")
    print(f"  feed/latest.json")

if __name__ == "__main__":
    main()
