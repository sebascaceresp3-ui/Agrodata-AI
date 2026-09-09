import streamlit as st
from utils.metrics import compact

def inject_css():
    st.markdown("""<style>
    :root{
      --navy:#10243e;--navy-2:#163354;--green:#1f8a62;--green-2:#27a779;
      --blue:#2f6fed;--gold:#e6a735;--canvas:#f3f5f8;--line:#e4e8ee;
      --ink:#182230;--muted:#667085;--white:#ffffff;
    }
    html,body,[class*="css"]{font-family:Inter,"Segoe UI",Arial,sans-serif}
    .stApp{background:var(--canvas);color:var(--ink)}
    .block-container{max-width:1600px;padding:3.5rem 1.65rem 2.5rem}
    header[data-testid="stHeader"]{background:#f3f5f8;color:#182230}

    /* Sidebar: compact analytical control rail */
    section[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--navy) 0%,#0b1b30 100%);border-right:0}
    section[data-testid="stSidebar"]>div{padding-top:1.15rem}
    section[data-testid="stSidebar"] *{color:#f8fafc}
    section[data-testid="stSidebar"] h2{font-size:1.06rem;letter-spacing:.02em;margin-bottom:.8rem}
    section[data-testid="stSidebar"] label p{font-size:.82rem;font-weight:600;color:#d7e1ec}
    section[data-testid="stSidebar"] [data-baseweb="select"]>div,
    section[data-testid="stSidebar"] [data-testid="stMultiSelect"]>div>div{
      background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.18);border-radius:7px
    }
    section[data-testid="stSidebar"] [data-testid="stSlider"] [role="slider"]{background:var(--green-2)}
    section[data-testid="stSidebar"] .stButton button{
      background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:7px;font-weight:600
    }
    section[data-testid="stSidebar"] .stButton button:hover{background:rgba(255,255,255,.14);border-color:#fff}

    /* Header */
    .hero{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 20px;
      border-radius:10px;background:linear-gradient(110deg,var(--navy) 0%,#194a55 70%,#1f8a62 100%);
      box-shadow:0 5px 18px rgba(16,36,62,.16);margin-bottom:9px;position:relative;overflow:hidden}
    .hero:after{content:"";position:absolute;right:-45px;top:-65px;width:190px;height:190px;border-radius:50%;border:32px solid rgba(255,255,255,.06)}
    .brand-lockup{display:flex;align-items:center;gap:13px;z-index:1}.brand-mark{display:grid;place-items:center;width:42px;height:42px;
      border-radius:9px;background:rgba(255,255,255,.13);font-size:1.35rem;border:1px solid rgba(255,255,255,.2)}
    .hero h1{color:white!important;margin:0;font-size:1.48rem;line-height:1.1;letter-spacing:-.02em}
    .hero p{margin:4px 0 0;color:#d8ebe5;font-size:.84rem}
    .hero-status{display:flex;align-items:center;gap:7px;color:#eaf7f2;font-size:.78rem;font-weight:600;z-index:1;
      background:rgba(8,31,43,.28);border:1px solid rgba(255,255,255,.15);padding:7px 10px;border-radius:999px}
    .status-dot{width:7px;height:7px;border-radius:50%;background:#5ce1a5;box-shadow:0 0 0 4px rgba(92,225,165,.12)}

    /* KPI cards */
    [data-testid="stMetric"]{background:var(--white);border:1px solid var(--line);border-radius:9px;padding:14px 15px 12px;
      min-height:116px;box-shadow:0 2px 7px rgba(16,36,62,.055);position:relative;overflow:hidden}
    [data-testid="stMetric"]:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--green)}
    [data-testid="stMetric"] label{font-size:.74rem!important;text-transform:uppercase;letter-spacing:.045em;font-weight:700;color:var(--muted)!important}
    [data-testid="stMetricValue"]{font-size:1.47rem;font-weight:700;color:var(--ink);letter-spacing:-.025em;padding-top:5px}
    [data-testid="stMetricDelta"]{font-size:.75rem;font-weight:600}

    h1,h2,h3{color:var(--ink);letter-spacing:-.015em}
    h2{font-size:1.25rem!important}h3{font-size:1rem!important;font-weight:700!important;margin-top:.2rem!important}
    [data-testid="stCaptionContainer"]{color:var(--muted);font-size:.76rem}
    [data-testid="stCaptionContainer"] p{color:#586579!important}
    hr{border-color:var(--line)}

    /* Report navigation */
    .stTabs [data-baseweb="tab-list"]{gap:4px;background:white;border:1px solid var(--line);padding:4px;border-radius:9px;box-shadow:0 1px 3px rgba(16,36,62,.04)}
    .stTabs [data-baseweb="tab"]{height:38px;border-radius:6px;padding:0 15px;font-size:.84rem;font-weight:600;color:var(--muted)}
    .stTabs [aria-selected="true"]{background:#eaf5f1!important;color:#176849!important}
    .stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}
    .stTabs [data-baseweb="tab-panel"]{padding-top:1rem}

    /* Visual containers */
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"]{
      background:white;border:1px solid var(--line);border-radius:9px;padding:8px;box-shadow:0 2px 7px rgba(16,36,62,.045)
    }
    [data-testid="stAlert"]{border-radius:8px;border-width:1px;font-size:.86rem}
    .stDownloadButton button,.stMainBlockContainer .stButton button{
      border-radius:7px;font-weight:600;border-color:#ccd4df;min-height:39px
    }
    .stDownloadButton button:hover,.stMainBlockContainer .stButton button:hover{border-color:var(--green);color:var(--green)}
    input,textarea{border-radius:7px!important}

    @media(max-width:900px){
      .block-container{padding:3.5rem .8rem 2rem}.hero{align-items:flex-start}.hero-status{display:none}
      [data-testid="stMetric"]{min-height:104px}.stTabs [data-baseweb="tab"]{padding:0 9px;font-size:.76rem}
      .stTabs [data-baseweb="tab-list"]{overflow-x:auto;flex-wrap:nowrap}
    }
    </style>""",unsafe_allow_html=True)

def metric_card(label, value, unit="", delta=None):
    shown=f"{compact(value)} {unit}" if value is not None else "N/D"
    if value is not None and unit == "º":
        shown = f"{int(value)}.º"
    st.metric(label,shown,None if delta is None else f"{delta:+.2f}% vs. año anterior")
