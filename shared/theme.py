"""
shared/theme.py
══════════════════════════════════════════════════════════════════════
Bayantx360 Suite — Unified Design System
══════════════════════════════════════════════════════════════════════

Single CSS string + Plotly theme used by all apps in the suite.
Ensures pixel-perfect visual consistency across PanelStatX,
DataSynthX, EFActor, and any future apps added to the suite.

Usage in each app:
    from shared.theme import apply_suite_css, apply_theme, PLOTLY_THEME
    apply_suite_css()          # call once, after st.set_page_config()
    fig = apply_theme(fig)     # wrap every Plotly figure
"""

import streamlit as st


# ── Design tokens ──────────────────────────────────────────────────────────────
TOKENS = {
    "bg":       "#0a0c10",
    "surface":  "#111318",
    "surface2": "#181c24",
    "border":   "#1f2535",
    "accent":   "#00e5c8",   # teal — primary CTA, highlights
    "accent2":  "#7c6df0",   # purple — secondary accent
    "accent3":  "#f05c7c",   # pink — danger / locked
    "text":     "#e2e8f4",
    "muted":    "#6b7a9a",
    "success":  "#22d3a0",
    "warn":     "#f5a623",
}


# ── Plotly theme ───────────────────────────────────────────────────────────────
PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Mono, monospace", color="#6b7a9a", size=11),
    xaxis=dict(
        gridcolor="#1f2535", linecolor="#1f2535",
        zerolinecolor="#1f2535", tickfont=dict(color="#6b7a9a"),
    ),
    yaxis=dict(
        gridcolor="#1f2535", linecolor="#1f2535",
        zerolinecolor="#1f2535", tickfont=dict(color="#6b7a9a"),
    ),
    colorway=["#00e5c8", "#7c6df0", "#f05c7c", "#f5a623", "#22d3a0", "#60a5fa"],
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color="#6b7a9a", size=10),
    ),
)


def apply_theme(fig):
    """Apply the suite Plotly theme to a figure. Returns the figure."""
    fig.update_layout(**PLOTLY_THEME)
    return fig


# ── Suite CSS ──────────────────────────────────────────────────────────────────
SUITE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Syne:wght@400;500;600;700;800&family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&display=swap');

/* ── Design tokens ── */
:root {
    --bg:       #0a0c10;
    --surface:  #111318;
    --surface2: #181c24;
    --border:   #1f2535;
    --accent:   #00e5c8;
    --accent2:  #7c6df0;
    --accent3:  #f05c7c;
    --text:     #e2e8f4;
    --muted:    #6b7a9a;
    --success:  #22d3a0;
    --warn:     #f5a623;
    --mono:     'DM Mono', monospace;
    --display:  'Syne', sans-serif;
    --hero-font:'Bricolage Grotesque', sans-serif;
}

/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebarNav"] { display: none !important; }

/* ── Headers ── */
h1, h2, h3, h4 {
    font-family: var(--display) !important;
    color: var(--text) !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 18px !important;
}
[data-testid="metric-container"] > div > div:first-child,
[data-testid="metric-container"] label {
    color: var(--muted) !important;
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
}
[data-testid="stMetricValue"] {
    color: var(--accent) !important;
    font-family: var(--display) !important;
    font-weight: 700 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid var(--accent) !important;
    color: var(--accent) !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    border-radius: 6px !important;
    padding: 8px 20px !important;
    transition: all 0.2s !important;
    letter-spacing: 0.05em !important;
}
.stButton > button:hover {
    background: var(--accent) !important;
    color: var(--bg) !important;
}
[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, #00bfab 100%) !important;
    border: none !important;
    color: #04090f !important;
    font-family: var(--display) !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 20px rgba(0,229,200,0.25) !important;
}
[data-testid="baseButton-primary"]:hover {
    box-shadow: 0 7px 28px rgba(0,229,200,0.45) !important;
    transform: translateY(-1px) !important;
}

/* ── Inputs & selects ── */
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    border-radius: 6px !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(0,229,200,0.45) !important;
    box-shadow: 0 0 0 3px rgba(0,229,200,0.07) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
    border-radius: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    color: var(--muted) !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    background: transparent !important;
    border-radius: 0 !important;
    padding: 12px 24px !important;
    letter-spacing: 0.04em !important;
    transition: color 0.2s !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; }

/* ── Dataframes ── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: var(--surface2) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
}
.streamlit-expanderContent {
    border: 1px solid var(--border) !important;
    border-top: none !important;
    background: var(--surface2) !important;
}

/* ── Sidebar labels ── */
.stSidebar label, .stSidebar .stMarkdown,
[data-testid="stSidebar"] label {
    color: var(--muted) !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.04em !important;
}

/* ── Slider ── */
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background: var(--accent) !important;
}

/* ── Radio ── */
.stRadio > div { gap: 8px !important; }
.stRadio label {
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    color: var(--text) !important;
}

/* ── Alerts ── */
[data-testid="stInfo"]    { background: rgba(0,229,200,0.06) !important; border-left-color: var(--accent) !important; }
[data-testid="stWarning"] { background: rgba(245,166,35,0.06) !important; border-left-color: var(--warn) !important; }
[data-testid="stSuccess"] { background: rgba(34,211,160,0.06) !important; border-left-color: var(--success) !important; }
[data-testid="stError"]   { background: rgba(240,92,124,0.06) !important; border-left-color: var(--accent3) !important; }

/* ── Dividers ── */
hr { border-color: var(--border) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar       { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* ══════════════════════════════════════════════
   SHARED COMPONENT CLASSES
   (used via st.markdown in all apps)
══════════════════════════════════════════════ */

/* Badge */
.badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 20px; font-size: 0.65rem;
    font-family: var(--mono); letter-spacing: 0.06em;
    text-transform: uppercase;
}
.badge-teal   { background: rgba(0,229,200,0.1);  color: var(--accent);  border: 1px solid rgba(0,229,200,0.25); }
.badge-purple { background: rgba(124,109,240,0.1); color: var(--accent2); border: 1px solid rgba(124,109,240,0.25); }
.badge-red    { background: rgba(240,92,124,0.1);  color: var(--accent3); border: 1px solid rgba(240,92,124,0.25); }
.badge-warn   { background: rgba(245,166,35,0.1);  color: var(--warn);    border: 1px solid rgba(245,166,35,0.25); }
.badge-green  { background: rgba(34,211,160,0.1);  color: var(--success); border: 1px solid rgba(34,211,160,0.25); }

/* AI output box */
.ai-box {
    background: linear-gradient(135deg, rgba(0,229,200,0.04) 0%, rgba(124,109,240,0.06) 100%);
    border: 1px solid rgba(0,229,200,0.2);
    border-left: 3px solid var(--accent);
    border-radius: 10px; padding: 20px 24px;
    font-family: var(--mono); font-size: 0.84rem;
    line-height: 1.85; color: var(--text); white-space: pre-wrap;
}
.ai-label {
    font-family: var(--display); font-size: 0.62rem;
    letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--accent); margin-bottom: 12px;
    display: flex; align-items: center; gap: 6px;
}

/* Locked feature banner */
.locked-banner {
    background: rgba(240,92,124,0.06);
    border: 1px solid rgba(240,92,124,0.2);
    border-left: 3px solid var(--accent3);
    border-radius: 10px; padding: 16px 20px;
    font-family: var(--mono); font-size: 0.78rem;
    color: var(--accent3); line-height: 1.7;
}
.locked-banner strong { color: var(--text); }

/* Section card */
.scard {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px; padding: 22px;
    margin-bottom: 16px;
}
.scard-title {
    font-family: var(--display); font-size: 0.78rem;
    font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.1em; color: var(--muted);
    margin-bottom: 14px;
}

/* Stat pill */
.stat-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 6px; padding: 5px 13px;
    font-size: 0.68rem; color: var(--muted);
    margin-right: 8px; margin-top: 10px;
    font-family: var(--mono);
}
.stat-pill b { color: var(--accent); }

/* App hero header */
.app-hero {
    padding: 24px 0 18px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 26px;
}
.app-hero-title {
    font-family: var(--display); font-size: 2rem;
    font-weight: 800; letter-spacing: -0.025em;
    color: var(--text); margin: 0; line-height: 1;
}
.app-hero-title span { color: var(--accent); }
.app-hero-sub {
    font-family: var(--mono); font-size: 0.72rem;
    color: var(--muted); margin-top: 6px; letter-spacing: 0.05em;
}

/* Suite nav breadcrumb (shown inside each app) */
.suite-nav {
    display: flex; align-items: center; gap: 10px;
    font-family: var(--mono); font-size: 0.62rem;
    color: var(--muted); padding: 10px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
}
.suite-nav a { color: var(--accent); text-decoration: none; }
.suite-nav a:hover { text-decoration: underline; }
.suite-nav-sep { color: var(--border); }

/* Spinner blink */
.spinner-dot::after { content: '●'; animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
</style>
"""


def apply_suite_css():
    """
    Inject the unified suite CSS into the Streamlit page.
    Call once per app, immediately after st.set_page_config().
    """
    st.markdown(SUITE_CSS, unsafe_allow_html=True)


# ── Shared UI components ───────────────────────────────────────────────────────

def render_app_hero(title_prefix: str, title_accent: str, subtitle: str):
    """Render the standard app hero header."""
    st.markdown(f"""
    <div class="app-hero">
        <div class="app-hero-title">{title_prefix}<span>{title_accent}</span></div>
        <div class="app-hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def render_locked_banner(feature_name: str, is_trial_user: bool):
    """
    Render a locked-feature banner.
    `is_trial_user` — True = trial message, False = no-credits message.
    """
    if is_trial_user:
        msg = (
            f"<strong>{feature_name}</strong> is not available on the Free Trial. "
            "Upgrade to a paid plan to unlock this feature across the entire Bayantx360 Suite."
        )
    else:
        msg = (
            f"<strong>{feature_name}</strong> requires credits. "
            "Your balance is exhausted — purchase more to continue."
        )
    st.markdown(f'<div class="locked-banner">🔒 {msg}</div>', unsafe_allow_html=True)


def render_credit_cost_caption(credits_left: int, cost: int = 1):
    """Render the small 'costs N credit · X remaining' caption under premium buttons."""
    noun = "credit" if cost == 1 else "credits"
    st.caption(f"⚡ Costs {cost} {noun} · {credits_left} remaining")
