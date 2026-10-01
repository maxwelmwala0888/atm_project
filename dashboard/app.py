"""ATM Network Operations Dashboard — CSV mode (Streamlit Cloud ready)."""
import os, json
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="ATM Network Ops", page_icon="🏧", layout="wide")

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

st.title("🏧 ATM Network Operations")
st.caption(f"Live view · {datetime.utcnow():%A %d %B %Y, %H:%M UTC}")

total_atms = len(dim)
total_tx   = int(dim["total_tx"].sum()) if "total_tx" in dim.columns else 0
avg_fail   = dim["failure_rate"].mean() if "failure_rate" in dim.columns else 0
critical   = 0
if len(cash) and "cash_status" in cash.columns:
    latest = cash[cash["event_date"] == cash["event_date"].max()]
    critical = int(latest["cash_status"].isin(["critical","low"]).sum())

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Active ATMs", total_atms)
c2.metric("Transactions", f"{total_tx:,}")
c3.metric("Failure rate", f"{avg_fail*100:.2f}%")
c4.metric("Active alerts", feed.get("total_alerts", 0))
c5.metric("Cash at risk", critical)

st.divider()
tab_ov, tab_al, tab_atm, tab_fl = st.tabs(["📊 Overview","🔔 Alerts","🏧 ATMs","⚙️ Faults"])

with tab_ov:
    cm, cs = st.columns([2,1])
    with cm:
        st.markdown("##### Network Map (scatter)")
        if len(dim) and {"latitude","longitude"}.issubset(dim.columns):
            if len(cash):
                latest = cash[cash["event_date"] == cash["event_date"].max()]
                merged = dim.merge(latest[["atm_id","min_cash_mwk","cash_status"]],
                                   on="atm_id", how="left")
            else:
                merged = dim.copy(); merged["cash_status"]="healthy"; merged["min_cash_mwk"]=0
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

with tab_atm:
    st.markdown("##### ATM Explorer")
    if len(dim):
        sel = st.selectbox("Pick an ATM", sorted(dim["atm_id"].unique()))
        row = dim[dim["atm_id"] == sel].iloc[0]
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
        st.dataframe(dim[["atm_id","city","region","atm_type","total_tx",
                          "lifetime_faults","failure_rate"]],
                     use_container_width=True, hide_index=True, height=280)

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
st.caption(f"ATM Network Analytics · {datetime.utcnow():%Y-%m-%d %H:%M UTC}")
