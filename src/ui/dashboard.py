"""
Green FinOps Dashboard — Streamlit UI
----------------------------------------
Design direction: dark, data-dense "financial terminal" aesthetic with a
single disciplined green accent (doing double duty for "$ saved" and
"CO2 avoided"), inspired by 2026 dark-mode analytics/fintech dashboard
conventions — near-black surfaces, high-contrast KPI numbers, muted
secondary text, one accent color reserved for positive/actionable signals,
amber/red reserved strictly for severity.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src.pipeline import run_pipeline

# ---------------------------------------------------------------------------
# Page config + theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Green FinOps Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG = "#0A0E0D"
SURFACE = "#12211B"
SURFACE_ALT = "#0E1613"
BORDER = "#1F3A2E"
TEXT = "#E8F0EB"
MUTED = "#8FA79A"
ACCENT = "#34D399"
ACCENT_DIM = "#1F6B4E"
WARNING = "#F5B841"
DANGER = "#F0665A"
CHART_SEQUENCE = ["#34D399", "#5EEAD4", "#F5B841", "#F0665A", "#7DD3FC", "#A78BFA"]

CUSTOM_CSS = f"""
<style>
    .stApp {{
        background-color: {BG};
        color: {TEXT};
    }}
    #MainMenu, footer, header {{visibility: hidden;}}

    section[data-testid="stSidebar"] {{
        background-color: {SURFACE_ALT};
        border-right: 1px solid {BORDER};
    }}

    h1, h2, h3, h4 {{
        color: {TEXT} !important;
        font-family: 'Segoe UI', -apple-system, sans-serif;
        letter-spacing: -0.02em;
    }}

    p, span, label, .stMarkdown {{
        color: {MUTED};
    }}

    div[data-testid="stMetric"] {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 18px 20px 14px 20px;
    }}
    div[data-testid="stMetricLabel"] {{
        color: {MUTED} !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}
    div[data-testid="stMetricValue"] {{
        color: {ACCENT} !important;
        font-size: 1.85rem !important;
        font-weight: 700;
    }}

    .banner {{
        background: linear-gradient(135deg, {SURFACE} 0%, {SURFACE_ALT} 100%);
        border: 1px solid {BORDER};
        border-left: 4px solid {ACCENT};
        border-radius: 10px;
        padding: 18px 22px;
        margin-bottom: 18px;
        color: {TEXT};
        font-size: 1.02rem;
        line-height: 1.55;
    }}

    .rec-card {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-left: 4px solid var(--sev-color);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        font-size: 0.92rem;
        color: {TEXT};
    }}

    .accuracy-pill {{
        display: inline-block;
        background-color: {SURFACE};
        border: 1px solid {ACCENT_DIM};
        border-radius: 20px;
        padding: 6px 16px;
        margin-right: 8px;
        font-size: 0.85rem;
        color: {ACCENT};
        font-weight: 600;
    }}

    .stDataFrame {{
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}

    div[data-testid="stExpander"] {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}

    .footer-credit {{
        text-align: center;
        color: {MUTED};
        font-size: 0.8rem;
        padding-top: 24px;
        border-top: 1px solid {BORDER};
        margin-top: 32px;
    }}
</style>
"""

PLOTLY_LAYOUT = dict(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(color=TEXT, family="Segoe UI, sans-serif"),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def severity_color(severity: str) -> str:
    return {"Critical": DANGER, "High": WARNING, "Moderate": ACCENT}.get(severity, ACCENT)


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # --- Header ---
    col_title, col_meta = st.columns([3, 1])
    with col_title:
        st.markdown("## 🌿 Green FinOps Dashboard")
        st.markdown(
            f"<span style='color:{MUTED}'>Cloud waste & carbon intelligence — "
            f"CodeCarbon-style SCI methodology, zero paid APIs</span>",
            unsafe_allow_html=True,
        )
    with col_meta:
        st.markdown(
            f"<div style='text-align:right; color:{MUTED}; font-size:0.85rem; padding-top:10px'>"
            f"Prepared by <b style='color:{TEXT}'>Ankita Mondal</b><br>"
            f"Sister Nivedita University</div>",
            unsafe_allow_html=True,
        )

    with st.spinner("Running detection + carbon/cost engine..."):
        data = run_pipeline()

    # --- Sidebar filters ---
    st.sidebar.markdown("### Filters")
    all_regions = sorted(
        set(data["flagged_instances"]["region"].tolist() if len(data["flagged_instances"]) else [])
        | set(data["flagged_storage"]["region"].tolist() if len(data["flagged_storage"]) else [])
    )
    selected_regions = st.sidebar.multiselect("Region", options=all_regions, default=all_regions)

    st.sidebar.markdown("### Detection Thresholds")
    st.sidebar.markdown(
        f"<span style='color:{MUTED}; font-size:0.85rem'>"
        f"Idle CPU mean &lt; 10% AND idle &gt;90% of observed hours<br>"
        f"Stale storage: unaccessed &gt; 90 days</span>",
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### Methodology")
    with st.sidebar.expander("How carbon is calculated"):
        st.markdown(
            f"<span style='color:{MUTED}; font-size:0.82rem'>"
            "Uses the Cloud Jewels / Cloud Carbon Footprint linear power "
            "model: AvgWatts = MinWatts + Utilization × (MaxWatts − MinWatts), "
            "Energy = AvgWatts × Hours × PUE (1.58), "
            "Carbon = Energy × Regional Grid Intensity.</span>",
            unsafe_allow_html=True,
        )

    flagged_inst = data["flagged_instances"]
    flagged_store = data["flagged_storage"]
    if selected_regions:
        flagged_inst = flagged_inst[flagged_inst["region"].isin(selected_regions)] if len(flagged_inst) else flagged_inst
        flagged_store = flagged_store[flagged_store["region"].isin(selected_regions)] if len(flagged_store) else flagged_store

    filtered_monthly = (
        (flagged_inst["monthly_waste_usd"].sum() if len(flagged_inst) else 0)
        + (flagged_store["monthly_waste_usd"].sum() if len(flagged_store) else 0)
    )
    filtered_annual = filtered_monthly * 12
    filtered_carbon = (
        (flagged_inst["monthly_carbon_kg_co2e"].sum() if len(flagged_inst) else 0)
        + (flagged_store["monthly_carbon_kg_co2e"].sum() if len(flagged_store) else 0)
    )

    # --- Fleet summary banner ---
    st.markdown(f"<div class='banner'>{data['fleet_summary_text']}</div>", unsafe_allow_html=True)

    # --- KPI row ---
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Monthly $ Waste", f"${filtered_monthly:,.2f}")
    k2.metric("Annual $ Waste", f"${filtered_annual:,.2f}")
    k3.metric("Monthly CO2e", f"{filtered_carbon:.2f} kg")
    k4.metric("Idle Instances", f"{len(flagged_inst)}")
    k5.metric("Stale Buckets", f"{len(flagged_store)}")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Charts row ---
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Top Waste Sources (Monthly $)")
        combined = []
        if len(flagged_inst):
            combined.append(
                flagged_inst[["instance_id", "monthly_waste_usd", "region"]].rename(
                    columns={"instance_id": "resource"}
                ).assign(type="Compute")
            )
        if len(flagged_store):
            combined.append(
                flagged_store[["bucket_id", "monthly_waste_usd", "region"]].rename(
                    columns={"bucket_id": "resource"}
                ).assign(type="Storage")
            )
        if combined:
            top_df = pd.concat(combined).sort_values("monthly_waste_usd", ascending=False).head(10)
            fig = px.bar(
                top_df.sort_values("monthly_waste_usd"),
                x="monthly_waste_usd",
                y="resource",
                color="type",
                orientation="h",
                color_discrete_sequence=CHART_SEQUENCE,
                labels={"monthly_waste_usd": "Monthly $ Waste", "resource": ""},
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No flagged waste in current filter selection.")

    with c2:
        st.markdown("#### Waste by Region")
        region_data = []
        if len(flagged_inst):
            region_data.append(flagged_inst.groupby("region")["monthly_waste_usd"].sum())
        if len(flagged_store):
            region_data.append(flagged_store.groupby("region")["monthly_waste_usd"].sum())
        if region_data:
            region_totals = pd.concat(region_data).groupby(level=0).sum().reset_index()
            region_totals.columns = ["region", "monthly_waste_usd"]
            fig2 = px.pie(
                region_totals,
                names="region",
                values="monthly_waste_usd",
                hole=0.55,
                color_discrete_sequence=CHART_SEQUENCE,
            )
            fig2.update_layout(**PLOTLY_LAYOUT, height=380)
            fig2.update_traces(textfont_color=TEXT)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No flagged waste in current filter selection.")

    # --- CPU utilization explorer ---
    st.markdown("#### Fleet CPU Utilization — Idle vs Healthy")
    all_inst = data["all_instances"]
    fig3 = px.scatter(
        all_inst,
        x="mean_cpu_pct",
        y="hourly_cost_usd",
        color="is_flagged_idle",
        size="vcpu",
        hover_data=["instance_id", "instance_type", "region"],
        color_discrete_map={True: DANGER, False: ACCENT},
        labels={
            "mean_cpu_pct": "Mean CPU Utilization (%)",
            "hourly_cost_usd": "Hourly Cost (USD)",
            "is_flagged_idle": "Flagged Idle",
        },
    )
    fig3.update_layout(**PLOTLY_LAYOUT, height=380)
    st.plotly_chart(fig3, use_container_width=True)

    # --- Recommendations feed ---
    st.markdown("#### Actionable Recommendations")
    recs = data["recommendations"]
    if len(selected_regions) < len(all_regions) and len(recs):
        recs = recs[recs["region"].isin(selected_regions)]

    if len(recs) == 0:
        st.info("No recommendations for the current filter selection.")
    else:
        for _, row in recs.iterrows():
            color = severity_color(row["severity"])
            st.markdown(
                f"<div class='rec-card' style='--sev-color:{color}'>{row['recommendation']}</div>",
                unsafe_allow_html=True,
            )

    # --- Model validation / accuracy panel ---
    st.markdown("#### Detection Accuracy (validated against synthetic ground truth)")
    st.markdown(
        f"<span style='color:{MUTED}; font-size:0.85rem'>"
        "Note: precision/recall are computed against labels embedded in the "
        "synthetic mock data for validation purposes only — real telemetry "
        "has no ground truth.</span>",
        unsafe_allow_html=True,
    )
    ca, sa = data["compute_accuracy"], data["storage_accuracy"]
    pill_html = (
        f"<div style='margin-top:8px'>"
        f"<span class='accuracy-pill'>Compute Precision: {ca['precision']*100:.0f}%</span>"
        f"<span class='accuracy-pill'>Compute Recall: {ca['recall']*100:.0f}%</span>"
        f"<span class='accuracy-pill'>Compute F1: {ca['f1_score']*100:.0f}%</span>"
        f"<span class='accuracy-pill'>Storage Precision: {sa['precision']*100:.0f}%</span>"
        f"<span class='accuracy-pill'>Storage Recall: {sa['recall']*100:.0f}%</span>"
        f"</div>"
    )
    st.markdown(pill_html, unsafe_allow_html=True)

    with st.expander("View raw flagged data tables"):
        t1, t2 = st.tabs(["Idle Instances", "Stale Storage"])
        with t1:
            st.dataframe(flagged_inst, use_container_width=True)
        with t2:
            st.dataframe(flagged_store, use_container_width=True)

    st.markdown(
        f"<div class='footer-credit'>Green FinOps Dashboard · Built for the 1M1B AI for "
        f"Sustainability Internship (IBM SkillsBuild & AICTE) · SDG 7 / 12 / 13 · "
        f"Ankita Mondal, Sister Nivedita University</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
