"""FireWatch dashboard entry point and shared navigation shell."""

import streamlit as st


st.set_page_config(
    page_title="FireWatch | Global Fire Intelligence",
    page_icon=":material/local_fire_department:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #0b0f14; }
    [data-testid="stSidebar"] { background: #111820; border-right: 1px solid #25303b; }
    .block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
    .eyebrow { color: #fb923c; font-size: .78rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
    .page-header { display: block; min-width: 0; overflow: visible; margin: 0 0 1rem; }
    .page-eyebrow { display: block; box-sizing: border-box; max-width: 100%; overflow: visible; padding: 0 .04em .06em; color: #fb923c; font-size: .7rem; font-weight: 700; letter-spacing: .1em; line-height: 1.5; text-transform: uppercase; margin: 0 0 .35rem; white-space: normal; overflow-wrap: anywhere; }
    .page-title { color: #f8fafc; font-size: clamp(1.8rem, 3.2vw, 2.45rem); font-weight: 750; line-height: 1.16; margin: 0 0 .4rem; overflow-wrap: anywhere; }
    .page-description { color: #9aa8b7; font-size: clamp(.94rem, 1.1vw, 1rem); line-height: 1.55; margin: 0; max-width: 64rem; }
    .map-context-note { color: #cbd5e1; background: #111820; border: 1px solid #263442; border-left: 3px solid #f97316; border-radius: 9px; padding: .65rem .85rem; margin: .15rem 0 .8rem; font-size: .88rem; line-height: 1.5; }
    @media (max-width: 640px) {
        .block-container { padding-top: 1.35rem; }
        .page-header { margin-bottom: .8rem; }
        .page-eyebrow { letter-spacing: .075em; }
        .page-title { font-size: clamp(1.65rem, 7vw, 2rem); }
    }
    .meta-pill { display: inline-block; color: #cbd5e1; background: #151e28; border: 1px solid #283543; border-radius: 999px; padding: .38rem .75rem; margin: 0 .4rem .5rem 0; font-size: .82rem; }
    .kpi-card { background: linear-gradient(145deg, #151e28, #111820); border: 1px solid #263442; border-radius: 14px; padding: 1rem 1.1rem; min-height: 122px; box-shadow: 0 8px 22px rgba(0,0,0,.16); }
    .kpi-label { color: #9aa8b7; font-size: .77rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; }
    .kpi-value { color: #f8fafc; font-size: clamp(1.25rem, 2vw, 1.8rem); font-weight: 750; margin-top: .55rem; }
    .section-heading { color: #f1f5f9; font-size: 1.15rem; font-weight: 700; margin: .5rem 0 .2rem; }
    .section-note { color: #8b9aaa; font-size: .86rem; margin: 0 0 .8rem; }
    div[data-testid="stDataFrame"] { border: 1px solid #263442; border-radius: 12px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

page = st.navigation(
    [
        st.Page("pages/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
        st.Page("pages/global_fire_map.py", title="Fire Explorer", icon=":material/public:"),
        st.Page("pages/trends_insights.py", title="Trends & Insights", icon=":material/monitoring:"),
        st.Page("pages/live_monitoring.py", title="Live Monitoring", icon=":material/sensors:"),
    ],
    position="sidebar",
)

with st.sidebar:
    st.markdown("<div class='eyebrow'>FireWatch</div>", unsafe_allow_html=True)
    st.markdown("### Global Fire Intelligence")
    st.caption("NASA FIRMS Â· VIIRS S-NPP")
    st.divider()
    st.caption("Data period Â· 2025")

page.run()
