"""ATM Network Operations Dashboard — v2."""
import os, json
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="ATM Network Ops",
    page_icon="🏧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Custom CSS ----------
st.markdown("""
<style>
    .main-header {
        font-size: 2rem; font-weight: 700;
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header { color: #6b7280; font-size: 0.9rem; margin-top: -8px; }
    .metric-card {
        background: white; padding: 1rem; border-radius: 12px;
        border-left: 4px solid #2a5298;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .metric-card.warn { border-left-color: #f59e0b; }
    .metric-card.danger { border-left-color: #dc2626; }
    .metric-card.ok { border-left-color: #10b981; }
    .alert-p1 { background: #fee2e2; padding: 0.6rem 0.8rem; border-radius: 8px;
                border-left: 4px solid #dc2626; margin-bottom: 0.5rem; }
    .alert-p2 { background: #fef3c7; padding: 0.6rem 0.8rem; border-radius: 8px;
                border-left: 4px solid #f59e0b; margin-bottom: 0.5rem; }
    .alert-p3 { background: #fef9c3; padding: 0.6rem 0.8rem; border-radius: 8px;
                border-left: 4px solid #eab308; margin-bottom: 0.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 16px; font-weight: 500; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
</style>
""", unsafe_allow_html=True)

DB = dict(host="postgres", dbname="atm_warehouse", user="atm", password="atm_pass")
ALERTS = "/alerts/outbox/feed/latest.json"

@st.cache_data(ttl=30)
def query(sql):
    conn = psycopg2.connect(**DB)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def load_feed():
    if not os.path.exists(ALERTS):
        return {"total_alerts": 0, "by_type": {}, "by_priority": {}, "alerts": []}
    with open(ALERTS) as f:
        return json.load(f)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### 🎛️ Controls")
    refresh = st.button("🔄 Refresh data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last loaded: {datetime.utcnow():%H:%M:%S} UTC")

    st.divider()
    st.markdown("### 🔎 Filters")
    regions = query("SELECT DISTINCT region FROM gold.dim_atm_network ORDER BY 1")["region"].tolist()
    region_filter = st.multiselect("Region", regions, default=regions)

    atm_types = query("SELECT DISTINCT atm_type FROM gold.dim_atm_network ORDER BY 1")["atm_type"].tolist()
    type_filter = st.multiselect("ATM type", atm_types, default=atm_types)

    st.divider()
    st.markdown("### 📎 Links")
    st.markdown("- [MLflow](http://localhost:5000)")
    st.markdown("- [Airflow](http://localhost:8090)")
    st.markdown("- [Kafka UI](http://localhost:8080)")

# ---------- Header ----------
st.markdown('<h1 class="main-header">🏧 ATM Network Operations</h1>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-header">Live operational view · {datetime.utcnow():%A %d %B %Y, %H:%M UTC}</p>',
            unsafe_allow_html=True)

# ---------- Data ----------
net = query("""
    SELECT COUNT(*) AS atms,
           COALESCE(SUM(total_tx),0) AS total_tx,
           COALESCE(AVG(failure_rate),0) AS avg_failure_rate,
           COALESCE(SUM(lifetime_faults),0) AS total_faults
    FROM gold.dim_atm_network
""").iloc[0]

cash_status_df = query("""
    SELECT cash_status, COUNT(*) AS n
    FROM gold.fct_atm_daily_cash
    WHERE event_date = (SELECT MAX(event_date) FROM gold.fct_atm_daily_cash)
    GROUP BY cash_status
""")
cash_status = cash_status_df.set_index("cash_status")["n"].to_dict()

fault_today = query("""
    SELECT COALESCE(SUM(faults),0) AS f, COALESCE(SUM(warnings),0) AS w
    FROM gold.fct_atm_fault_events
    WHERE event_date = (SELECT MAX(event_date) FROM gold.fct_atm_fault_events)
""").iloc[0]

feed = load_feed()
critical_count = cash_status.get("critical", 0) + cash_status.get("low", 0)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🏧 Active ATMs", f"{int(net['atms'])}")
c2.metric("💳 Total transactions", f"{int(net['total_tx']):,}")
c3.metric("⚠️ Failure rate", f"{net['avg_failure_rate']*100:.2f}%")
c4.metric("🔔 Active alerts", f"{feed.get('total_alerts', 0)}",
          delta=f"{feed.get('by_priority',{}).get('P1',0)} P1" if feed.get('by_priority') else None,
          delta_color="inverse")
c5.metric("🟠 Cash at risk", f"{critical_count}")

st.divider()

tab_live, tab_overview, tab_alerts, tab_atms, tab_faults, tab_models = st.tabs(
    ["🔴 Live", "📊 Overview", "🔔 Alerts", "🏧 ATMs", "⚙️ Faults", "🤖 Models"]
)


# =================== TAB 0: LIVE ===================
with tab_live:
    st_autorefresh(interval=2000, key="live_refresh")

    st.markdown("##### 🔴 Live Transaction Stream")
    st.caption("Auto-refreshing every 2 seconds — data flows from Kafka → Postgres in real time")

    # top KPI cards
    live_stats = query("""
        SELECT
            COUNT(*) FILTER (WHERE event_ts > NOW() - INTERVAL '1 minute')  AS last_min,
            COUNT(*) FILTER (WHERE event_ts > NOW() - INTERVAL '1 hour')    AS last_hour,
            COUNT(*)                                                         AS total,
            COALESCE(SUM(amount_mwk) FILTER (WHERE event_ts > NOW() - INTERVAL '1 minute'), 0) AS vol_1m,
            COALESCE(SUM(amount_mwk) FILTER (WHERE event_ts > NOW() - INTERVAL '1 hour'), 0)   AS vol_1h
        FROM live.atm_transactions
    """).iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Transactions / min", f"{int(live_stats['last_min']):,}")
    k2.metric("Transactions / hour", f"{int(live_stats['last_hour']):,}")
    k3.metric("Volume / min (MWK)", f"{int(live_stats['vol_1m']):,}")
    k4.metric("Volume / hour (MWK)", f"{int(live_stats['vol_1h']):,}")

    st.divider()

    col_live, col_chart = st.columns([3, 2])

    with col_live:
        st.markdown("##### Last 15 transactions")
        last = query("""
            SELECT TO_CHAR(event_ts, 'HH24:MI:SS') AS time,
                   atm_id, tx_type, amount_mwk, card_type,
                   CASE WHEN success THEN '✅' ELSE '❌' END AS status
            FROM live.atm_transactions
            ORDER BY event_ts DESC
            LIMIT 15
        """)
        if len(last):
            st.dataframe(last, use_container_width=True, hide_index=True, height=520)
        else:
            st.info("Waiting for the first transaction...")

    with col_chart:
        st.markdown("##### Transactions per minute (last 15 min)")
        per_min = query("""
            SELECT DATE_TRUNC('minute', event_ts) AS minute,
                   COUNT(*) AS tx,
                   SUM(amount_mwk) AS volume
            FROM live.atm_transactions
            WHERE event_ts > NOW() - INTERVAL '15 minutes'
            GROUP BY 1 ORDER BY 1
        """)
        if len(per_min):
            fig = px.area(per_min, x="minute", y="tx",
                          labels={"tx": "transactions", "minute": ""})
            fig.update_traces(line_color="#dc2626", fillcolor="rgba(220,38,38,0.2)")
            fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.bar(per_min, x="minute", y="volume",
                          labels={"volume": "MWK", "minute": ""})
            fig2.update_traces(marker_color="#2a5298")
            fig2.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("##### Top ATMs by live volume (last 5 min)")
    top_live = query("""
        SELECT atm_id, COUNT(*) AS tx, SUM(amount_mwk) AS volume
        FROM live.atm_transactions
        WHERE event_ts > NOW() - INTERVAL '5 minutes'
        GROUP BY atm_id
        ORDER BY volume DESC NULLS LAST
        LIMIT 8
    """)
    if len(top_live):
        st.dataframe(top_live, use_container_width=True, hide_index=True)

# =================== TAB 1: OVERVIEW ===================
with tab_overview:
    col_map, col_status = st.columns([2, 1])

    with col_map:
        st.markdown("##### 🗺️ Network Map")
        cash_today = query(f"""
            SELECT d.atm_id, d.min_cash_mwk, d.cash_status, d.cash_ma_7d,
                   n.city, n.region, n.latitude, n.longitude, n.atm_type
            FROM gold.fct_atm_daily_cash d
            JOIN gold.dim_atm_network n USING (atm_id)
            WHERE d.event_date = (SELECT MAX(event_date) FROM gold.fct_atm_daily_cash)
              AND n.region = ANY(ARRAY{regions!r})
              AND n.atm_type = ANY(ARRAY{atm_types!r})
        """.replace("{regions!r}", str(region_filter)).replace("{atm_types!r}", str(type_filter)))

        color_map = {"critical": "#dc2626", "low": "#f59e0b", "healthy": "#10b981"}
        if len(cash_today):
            fig = px.scatter_map(
                cash_today, lat="latitude", lon="longitude",
                color="cash_status", color_discrete_map=color_map,
                hover_name="atm_id",
                hover_data={"city": True, "region": True,
                            "min_cash_mwk": ":,", "atm_type": True,
                            "latitude": False, "longitude": False},
                zoom=5, height=460, size_max=14,
            )
            fig.update_traces(marker=dict(size=16, opacity=0.85))
            fig.update_layout(map_style="open-street-map",
                              margin=dict(l=0, r=0, t=0, b=0),
                              legend=dict(orientation="h", y=1.02, x=0))
            st.plotly_chart(fig, use_container_width=True)

    with col_status:
        st.markdown("##### Cash health")
        if cash_status_df.shape[0]:
            st.plotly_chart(
                px.pie(cash_status_df, names="cash_status", values="n",
                       color="cash_status",
                       color_discrete_map=color_map, hole=0.55),
                use_container_width=True,
            )

        st.markdown("##### Faults today")
        st.markdown(
            f"<div class='metric-card danger'>"
            f"<b>{int(fault_today['f'])}</b> faults · "
            f"<b>{int(fault_today['w'])}</b> warnings"
            f"</div>", unsafe_allow_html=True
        )

# =================== TAB 2: ALERTS ===================
with tab_alerts:
    colA, colB = st.columns([2, 1])

    with colA:
        st.markdown("##### 🔔 Alert Feed")
        pri_filter = st.multiselect("Filter by priority",
                                     ["P1", "P2", "P3"],
                                     default=["P1", "P2", "P3"])

        filtered = [a for a in feed["alerts"] if a["priority"] in pri_filter]

        for a in filtered[:20]:
            cls = {"P1": "alert-p1", "P2": "alert-p2", "P3": "alert-p3"}.get(a["priority"], "alert-p3")
            st.markdown(
                f'<div class="{cls}">'
                f'<b>{a["priority"]} · {a["atm_id"]}</b> — {a["city"]}<br>'
                f'<span style="font-size:0.85rem">{a["message"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with colB:
        st.markdown("##### By priority")
        if feed.get("by_priority"):
            pri_df = pd.DataFrame([{"priority": k, "count": v}
                                    for k, v in feed["by_priority"].items()])
            st.plotly_chart(
                px.bar(pri_df, x="priority", y="count", color="priority",
                       color_discrete_map={"P1": "#dc2626", "P2": "#f59e0b", "P3": "#eab308"},
                       text="count"),
                use_container_width=True,
            )
        st.markdown("##### By type")
        if feed.get("by_type"):
            type_df = pd.DataFrame([{"type": k, "count": v}
                                     for k, v in feed["by_type"].items()])
            st.plotly_chart(
                px.pie(type_df, names="type", values="count", hole=0.55),
                use_container_width=True,
            )

# =================== TAB 3: ATMs ===================
with tab_atms:
    st.markdown("##### 🏧 ATM Explorer")
    atms_df = query("""
        SELECT n.atm_id, n.city, n.region, n.atm_type, n.atm_model,
               n.total_tx, n.failed_tx, n.failure_rate,
               n.lifetime_faults, n.avg_withdrawal_mwk
        FROM gold.dim_atm_network n
        ORDER BY n.total_tx DESC
    """)
    atms_df["failure_pct"] = (atms_df["failure_rate"] * 100).round(2)
    atms_df = atms_df.drop(columns=["failure_rate"])

    selected = st.selectbox("Pick an ATM for drill-down", atms_df["atm_id"].tolist())

    if selected:
        row = atms_df[atms_df["atm_id"] == selected].iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("City", row["city"])
        m2.metric("Type", row["atm_type"])
        m3.metric("Transactions", f"{int(row['total_tx']):,}")
        m4.metric("Failure rate", f"{row['failure_pct']}%")

        trend = query(f"""
            SELECT event_date, min_cash_mwk, avg_cash_mwk, cash_ma_7d,
                   total_withdrawal_mwk, cash_status
            FROM gold.fct_atm_daily_cash
            WHERE atm_id = '{selected}'
            ORDER BY event_date
        """)
        if len(trend):
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=trend["event_date"], y=trend["min_cash_mwk"],
                                      name="Min cash", mode="lines",
                                      line=dict(color="#dc2626", width=2)))
            fig.add_trace(go.Scatter(x=trend["event_date"], y=trend["cash_ma_7d"],
                                      name="7-day MA", mode="lines",
                                      line=dict(color="#2a5298", width=2)))
            fig.add_trace(go.Bar(x=trend["event_date"], y=trend["total_withdrawal_mwk"],
                                  name="Daily withdrawal", yaxis="y2", opacity=0.3))
            fig.update_layout(
                height=380, hovermode="x unified",
                yaxis=dict(title="Cash (MWK)"),
                yaxis2=dict(title="Withdrawal (MWK)", overlaying="y", side="right",
                            showgrid=False),
                legend=dict(orientation="h", y=1.1),
                margin=dict(l=0, r=0, t=20, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### All ATMs")
    st.dataframe(atms_df, use_container_width=True, hide_index=True, height=300)

# =================== TAB 4: FAULTS ===================
with tab_faults:
    st.markdown("##### ⚙️ Component Fault Distribution")

    comps = query("""
        SELECT atm_id,
               SUM(card_reader_events) AS card_reader,
               SUM(dispenser_events)   AS dispenser,
               SUM(printer_events)     AS printer,
               SUM(network_events)     AS network,
               SUM(display_events)     AS display,
               SUM(power_unit_events)  AS power_unit,
               SUM(sensors_events)     AS sensors
        FROM gold.fct_atm_fault_events
        GROUP BY atm_id
        ORDER BY atm_id
    """)

    if len(comps):
        heat = comps.set_index("atm_id")
        fig = px.imshow(heat.T, aspect="auto",
                        color_continuous_scale="Reds",
                        labels=dict(x="ATM", y="Component", color="Events"))
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Top 10 by 30-day fault MA")
        top = query("""
            SELECT atm_id, MAX(faults_ma_30d) AS faults_ma_30d
            FROM gold.fct_atm_fault_events
            GROUP BY atm_id
            ORDER BY faults_ma_30d DESC LIMIT 10
        """)
        fig = px.bar(top.sort_values("faults_ma_30d"),
                     x="faults_ma_30d", y="atm_id", orientation="h",
                     color="faults_ma_30d", color_continuous_scale="OrRd")
        fig.update_layout(height=350, showlegend=False,
                          coloraxis_showscale=False,
                          margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Severity breakdown")
        sev = query("""
            SELECT severity, COUNT(*) AS n
            FROM gold.fct_atm_fault_events
            GROUP BY severity
        """)
        if len(sev):
            fig = px.pie(sev, names="severity", values="n", hole=0.55,
                         color="severity",
                         color_discrete_map={"high": "#dc2626",
                                              "medium": "#f59e0b",
                                              "low": "#10b981"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

# =================== TAB 5: MODELS ===================
with tab_models:
    st.markdown("##### 🤖 ML Model Status")
    st.info("Live metrics are in MLflow → **[open http://localhost:5000](http://localhost:5000)**")

    col1, col2, col3 = st.columns(3)
    col1.markdown("""
    **Cash Forecast (Prophet)**
    - Experiment: `atm_cash_forecast`
    - 20 runs (one per ATM)
    - Metric: MAE
    - Output: 72h forecast
    """)
    col2.markdown("""
    **Fault Prediction (XGBoost)**
    - Experiment: `atm_fault_prediction`
    - Registered: `atm_fault_xgboost`
    - Metric: ROC-AUC, F1
    - Output: probability per ATM
    """)
    col3.markdown("""
    **Branch Clustering (KMeans)**
    - Experiment: `atm_branch_utilisation`
    - Registered: `atm_branch_kmeans`
    - Metric: Silhouette
    - Output: cluster labels
    """)

    st.divider()
    st.markdown("##### Pipeline DAG (Airflow)")
    st.markdown("""
    `produce → bronze → silver → dbt → alerts`

    Orchestrated by `atm_pipeline` in **[Airflow](http://localhost:8090)**.
    """)

st.divider()
st.caption("ATM Network Analytics · Data: gold schemas · "
           f"Rendered {datetime.utcnow():%Y-%m-%d %H:%M UTC}")
