"""ATM Network Operations Dashboard — CSV + simulated live."""
import os, json, time, random
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="ATM Network Ops", page_icon="🏧", layout="wide",
                   initial_sidebar_state="expanded")

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_REFRESH = True
except ImportError:
    HAS_REFRESH = False

BASE   = os.path.dirname(os.path.abspath(__file__))
DATA   = os.path.join(BASE, "..", "data", "gold_export")
ALERTS = os.path.join(BASE, "..", "alerts", "outbox", "feed", "latest.json")

@st.cache_data(ttl=300)
def load_csv(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return pd.DataFrame()
    df = pd.read_csv(p)
    for c in df.columns:
        if "date" in c.lower():
            try: df[c] = pd.to_datetime(df[c])
            except: pass
    return df

@st.cache_data(ttl=300)
def load_feed():
    if not os.path.exists(ALERTS):
        return {"total_alerts": 0, "by_type": {}, "by_priority": {}, "alerts": []}
    with open(ALERTS) as f:
        return json.load(f)

dim  = load_csv("dim_atm_network.csv")
cash = load_csv("fct_atm_daily_cash.csv")
flt  = load_csv("fct_atm_fault_events.csv")
feed = load_feed()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## 🎛️ Controls")
    auto = st.checkbox("Auto-refresh every 3s", value=True)
    if st.button("🔄 Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last loaded: {datetime.utcnow():%H:%M:%S} UTC")
    st.divider()

    st.markdown("### 🔎 Filters")
    if len(dim) and "region" in dim.columns:
        regions = ["All"] + sorted(dim["region"].dropna().unique().tolist())
        region = st.selectbox("Region", regions)
    else:
        region = "All"

    if len(dim) and "atm_type" in dim.columns:
        types = ["All"] + sorted(dim["atm_type"].dropna().unique().tolist())
        atype = st.selectbox("ATM type", types)
    else:
        atype = "All"

    st.divider()
    st.markdown("### 📎 Links")
    st.markdown("- [GitHub repo](https://github.com/maxwelmwala0888/atm_project)")
    st.caption("Data: gold exports · Live: Codespaces only")

# Apply filters
dim_f = dim.copy()
if region != "All" and "region" in dim_f.columns:
    dim_f = dim_f[dim_f["region"] == region]
if atype != "All" and "atm_type" in dim_f.columns:
    dim_f = dim_f[dim_f["atm_type"] == atype]

# ---------- Auto-refresh ----------
tick = int(time.time() // 3) if auto else 0
if HAS_REFRESH and auto:
    st_autorefresh(interval=3000, key="tick")

# ---------- Header ----------
st.markdown(
    '<h1 style="background:linear-gradient(90deg,#1e3c72,#2a5298);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
    'font-size:2rem;font-weight:700;margin-bottom:0">🏧 ATM Network Operations</h1>',
    unsafe_allow_html=True,
)
st.caption(f"Live view · {datetime.utcnow():%A %d %B %Y, %H:%M:%S UTC} · tick #{tick}")

# ---------- KPIs (with a little simulated drift) ----------
base_tx   = int(dim_f["total_tx"].sum()) if "total_tx" in dim_f.columns else 0
live_drift = (tick * 7) % 500          # adds 0..499 and cycles
total_tx   = base_tx + live_drift

avg_fail   = dim_f["failure_rate"].mean() if "failure_rate" in dim_f.columns else 0
critical   = 0
if len(cash) and "cash_status" in cash.columns:
    latest = cash[cash["event_date"] == cash["event_date"].max()]
    critical = int(latest["cash_status"].isin(["critical","low"]).sum())

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Active ATMs", len(dim_f))
c2.metric("Transactions", f"{total_tx:,}",
          delta=live_drift - ((tick-1)*7 % 500) if tick > 0 else 0,
          delta_color="normal")
c3.metric("Failure rate", f"{avg_fail*100:.2f}%")
c4.metric("Active alerts", feed.get("total_alerts", 0))
c5.metric("Cash at risk", critical)

st.divider()
tab_live, tab_ov, tab_al, tab_atm, tab_fl = st.tabs(
    ["🔴 Live (sim)", "📊 Overview", "🔔 Alerts", "🏧 ATMs", "⚙️ Faults"]
)

# ===== LIVE (simulated) =====
with tab_live:
    st.markdown("##### 🔴 Simulated Live Transaction Stream")
    st.caption("Streamlit Cloud can't reach Kafka — this rotates through the "
               "historical data to give a live-feed look. Real live data runs "
               "on the Codespaces demo with Kafka + Postgres.")

    # Build a fake rolling feed from the cash data
    if len(cash):
        seed = tick
        random.seed(seed)
        sample = cash.sample(min(15, len(cash)), random_state=seed)
        rows = []
        for i, r in sample.iterrows():
            rows.append({
                "time":   (datetime.utcnow() - timedelta(seconds=len(rows)*3)).strftime("%H:%M:%S"),
                "atm_id": r.get("atm_id","?"),
                "type":   random.choice(["withdrawal","deposit","balance_enquiry","transfer"]),
                "amount": f"{random.randint(500, 50000):,}",
                "status": "✅" if random.random() > 0.03 else "❌",
            })

        live_df = pd.DataFrame(rows)
        st.dataframe(live_df, use_container_width=True, hide_index=True, height=420)

    st.divider()
    st.markdown("##### 🔔 Latest alerts (from feed)")
    if feed.get("alerts"):
        for a in feed["alerts"][:5]:
            color  = {"P1":"#fee2e2","P2":"#fef3c7","P3":"#fef9c3"}.get(a["priority"],"#fef9c3")
            border = {"P1":"#dc2626","P2":"#f59e0b","P3":"#eab308"}.get(a["priority"],"#eab308")
            st.markdown(
                f'<div style="background:{color};padding:.6rem .8rem;border-radius:8px;'
                f'border-left:4px solid {border};margin-bottom:.5rem">'
                f'<b>{a["priority"]} · {a["atm_id"]}</b> — {a.get("city","")}<br>'
                f'<span style="font-size:.85rem">{a["message"]}</span></div>',
                unsafe_allow_html=True)

# ===== OVERVIEW =====
with tab_ov:
    cm, cs = st.columns([2,1])
    with cm:
        st.markdown("##### Network Map (scatter)")
        if len(dim_f) and {"latitude","longitude"}.issubset(dim_f.columns):
            if len(cash):
                latest = cash[cash["event_date"] == cash["event_date"].max()]
                merged = dim_f.merge(latest[["atm_id","min_cash_mwk","cash_status"]],
                                     on="atm_id", how="left")
            else:
                merged = dim_f.copy(); merged["cash_status"]="healthy"; merged["min_cash_mwk"]=0
            merged["cash_status"] = merged["cash_status"].fillna("healthy")
            cmap = {"critical":"#dc2626","low":"#f59e0b","healthy":"#10b981"}
            fig = px.scatter(merged, x="longitude", y="latitude",
                             color="cash_status", color_discrete_map=cmap,
                             hover_name="atm_id",
                             hover_data={"city":True,"region":True,"atm_type":True,
                                         "min_cash_mwk":True,"latitude":False,"longitude":False},
                             height=460)
            fig.update_traces(marker=dict(size=16, opacity=0.85))
            fig.update_layout(plot_bgcolor="#f9fafb",
                              xaxis_title="Longitude", yaxis_title="Latitude",
                              margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
    with cs:
        st.markdown("##### Cash health")
        if len(cash) and "cash_status" in cash.columns:
            latest = cash[cash["event_date"] == cash["event_date"].max()]
            dist = latest["cash_status"].value_counts().reset_index()
            dist.columns = ["status","n"]
            st.plotly_chart(px.pie(dist, names="status", values="n", hole=0.55,
                                   color="status",
                                   color_discrete_map={"critical":"#dc2626","low":"#f59e0b","healthy":"#10b981"}),
                            use_container_width=True)

# ===== ALERTS =====
with tab_al:
    cA, cB = st.columns([2,1])
    with cA:
        st.markdown("##### Alert Feed")
        pri = st.multiselect("Filter by priority", ["P1","P2","P3"], default=["P1","P2","P3"])
        filtered = [a for a in feed.get("alerts", []) if a.get("priority") in pri]
        for a in filtered[:25]:
            color  = {"P1":"#fee2e2","P2":"#fef3c7","P3":"#fef9c3"}.get(a["priority"],"#fef9c3")
            border = {"P1":"#dc2626","P2":"#f59e0b","P3":"#eab308"}.get(a["priority"],"#eab308")
            st.markdown(
                f'<div style="background:{color};padding:.6rem .8rem;border-radius:8px;'
                f'border-left:4px solid {border};margin-bottom:.5rem">'
                f'<b>{a["priority"]} · {a["atm_id"]}</b> — {a.get("city","")}<br>'
                f'<span style="font-size:.85rem">{a["message"]}</span></div>',
                unsafe_allow_html=True)
    with cB:
        if feed.get("by_priority"):
            pdf = pd.DataFrame([{"priority":k,"count":v} for k,v in feed["by_priority"].items()])
            st.plotly_chart(px.bar(pdf, x="priority", y="count", color="priority", text="count",
                                   color_discrete_map={"P1":"#dc2626","P2":"#f59e0b","P3":"#eab308"}),
                            use_container_width=True)
        if feed.get("by_type"):
            tdf = pd.DataFrame([{"type":k,"count":v} for k,v in feed["by_type"].items()])
            st.plotly_chart(px.pie(tdf, names="type", values="count", hole=0.55),
                            use_container_width=True)

# ===== ATMs =====
with tab_atm:
    st.markdown("##### ATM Explorer")
    if len(dim_f):
        sel = st.selectbox("Pick an ATM", sorted(dim_f["atm_id"].unique()))
        row = dim_f[dim_f["atm_id"] == sel].iloc[0]
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("City", row.get("city",""))
        m2.metric("Type", row.get("atm_type",""))
        m3.metric("Transactions", f"{int(row.get('total_tx',0)):,}")
        m4.metric("Lifetime faults", f"{int(row.get('lifetime_faults',0))}")
        tr = cash[cash["atm_id"] == sel].sort_values("event_date")
        if len(tr):
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tr["event_date"], y=tr["min_cash_mwk"],
                                     name="Min cash", line=dict(color="#dc2626", width=2)))
            if "cash_ma_7d" in tr.columns:
                fig.add_trace(go.Scatter(x=tr["event_date"], y=tr["cash_ma_7d"],
                                         name="7d MA", line=dict(color="#2a5298", width=2)))
            fig.update_layout(height=380, hovermode="x unified", yaxis_title="Cash (MWK)",
                              margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dim_f[["atm_id","city","region","atm_type","total_tx",
                            "lifetime_faults","failure_rate"]],
                     use_container_width=True, hide_index=True, height=280)

# ===== FAULTS =====
with tab_fl:
    st.markdown("##### Component Fault Distribution")
    if len(flt):
        comps = flt.groupby("atm_id").agg(
            card_reader=("card_reader_events","sum"),
            dispenser=("dispenser_events","sum"),
            printer=("printer_events","sum"),
            network=("network_events","sum")).reset_index()
        fig = px.imshow(comps.set_index("atm_id").T, aspect="auto",
                        color_continuous_scale="Reds",
                        labels=dict(x="ATM", y="Component", color="Events"))
        fig.update_layout(height=360, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            top = flt.groupby("atm_id")["faults_ma_30d"].max().reset_index().sort_values("faults_ma_30d").tail(10)
            st.plotly_chart(px.bar(top, x="faults_ma_30d", y="atm_id", orientation="h",
                                   color="faults_ma_30d", color_continuous_scale="OrRd"),
                            use_container_width=True)
        with c2:
            sev = flt["severity"].value_counts().reset_index()
            sev.columns = ["severity","n"]
            st.plotly_chart(px.pie(sev, names="severity", values="n", hole=0.55,
                                   color="severity",
                                   color_discrete_map={"high":"#dc2626","medium":"#f59e0b","low":"#10b981"}),
                            use_container_width=True)

st.divider()
st.caption("ATM Network Analytics · Streamlit Cloud · Simulated live mode")
