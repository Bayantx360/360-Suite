"""
suite_home.py
══════════════════════════════════════════════════════════════════════
Bayantx360 Suite — Landing Page, Auth Gate & App Selector
══════════════════════════════════════════════════════════════════════

Routing architecture (Streamlit V2 MPA):
  • st.navigation() must be the FIRST Streamlit call — before set_page_config.
  • render_home() is a callable passed to st.Page() to avoid the infinite
    re-exec loop that would occur if suite_home.py were registered by path.
  • _pg.run() activates the router; for the home URL it calls render_home().
  • Launch buttons set st.session_state["_goto"] + st.rerun(). _goto is
    consumed at the top of render_home() so st.switch_page() fires cleanly.
"""

import streamlit as st
import sys, os

# ── Path resolution so `shared` is importable ─────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from shared.auth import (
    init_session_state,
    activate_free_trial,
    process_key_login,
    sign_out,
    is_trial,
)

# ─────────────────────────────────────────────────────────────────────────────
# All home page content lives inside render_home() so it can be passed as a
# callable to st.Page(). This avoids re-exec'ing this file when _pg.run() fires.
# ─────────────────────────────────────────────────────────────────────────────
def render_home():
    """Landing page, auth gate, and app selector — all in one."""

    # Init session
    init_session_state()

    # Deferred navigation: consume _goto BEFORE any rendering so
    # st.switch_page() fires at the top of a clean rerun.
    _goto = st.session_state.pop("_goto", None)
    if _goto:
        st.switch_page(_goto)

    # ═══════════════════════════════════════════════════════════════════════════════
    # LANDING PAGE CSS
    # ═══════════════════════════════════════════════════════════════════════════════

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500&family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&display=swap');

    /* ── Tokens ── */
    :root {
        --bg:      #05070f;
        --s1:      #0b0e1a;
        --s2:      #10141f;
        --s3:      #161b28;
        --border:  rgba(255,255,255,0.06);
        --border2: rgba(255,255,255,0.11);
        --teal:    #00e5c8;
        --purple:  #7c6df0;
        --pink:    #f05c7c;
        --amber:   #f5a623;
        --text:    #e4eaf8;
        --text2:   #9aa3be;
        --muted:   #4e576e;
        --mono:    'DM Mono', monospace;
        --display: 'Bricolage Grotesque', sans-serif;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: var(--mono) !important;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    footer, #MainMenu, [data-testid="stToolbar"] { display: none !important; }
    [data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; }
    section.main > div { padding: 0 !important; }

    /* ── Ambient background ── */
    .lp-bg {
        position: fixed; inset: 0; z-index: 0;
        background: var(--bg);
    }
    .lp-bg::before {
        content: ''; position: absolute; inset: -60%;
        background:
            radial-gradient(ellipse 72% 55% at 50% -8%,  rgba(0,229,200,0.06) 0%, transparent 65%),
            radial-gradient(ellipse 55% 70% at 100% 60%, rgba(124,109,240,0.045) 0%, transparent 60%),
            radial-gradient(ellipse 45% 45% at 0% 80%,   rgba(0,229,200,0.028) 0%, transparent 55%);
        animation: bgDrift 30s ease-in-out infinite alternate;
    }
    @keyframes bgDrift { 0%{transform:scale(1) rotate(0deg)} 100%{transform:scale(1.06) rotate(1.5deg)} }

    .lp-grid {
        position: fixed; inset: 0; z-index: 0; pointer-events: none;
        background-image:
            linear-gradient(rgba(0,229,200,0.016) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,229,200,0.016) 1px, transparent 1px);
        background-size: 72px 72px;
        mask-image: radial-gradient(ellipse 80% 80% at 50% 40%, black 20%, transparent 80%);
    }

    /* ── All content above bg ── */
    .lp-wrap { position: relative; z-index: 10; }

    /* ── Animations ── */
    @keyframes fi { to { opacity: 1; transform: translateY(0); } }
    .fi { opacity: 0; transform: translateY(20px); animation: fi 0.65s cubic-bezier(0.22,1,0.36,1) forwards; }
    .d1{animation-delay:.05s} .d2{animation-delay:.12s} .d3{animation-delay:.20s}
    .d4{animation-delay:.28s} .d5{animation-delay:.36s} .d6{animation-delay:.44s}
    .d7{animation-delay:.52s} .d8{animation-delay:.60s}

    @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(.85)} }
    .dot-live {
        display: inline-block; width: 6px; height: 6px; border-radius: 50%;
        background: var(--teal); animation: pulse 2s ease-in-out infinite;
        vertical-align: middle; margin-right: 7px;
    }

    /* ── Navbar ── */
    .lp-nav {
        display: flex; align-items: center; justify-content: space-between;
        padding: 18px clamp(20px,5vw,64px);
        border-bottom: 1px solid var(--border);
        background: rgba(5,7,15,0.88);
        backdrop-filter: blur(24px);
        position: sticky; top: 0; z-index: 100;
    }
    .nav-brand {
        display: flex; align-items: center; gap: 12px;
        font-family: var(--display); font-weight: 800; font-size: 1.18rem;
        color: var(--text); letter-spacing: -0.03em;
    }
    .nav-logo {
        width: 34px; height: 34px; border-radius: 9px;
        background: linear-gradient(135deg, rgba(0,229,200,0.18), rgba(124,109,240,0.18));
        border: 1px solid rgba(0,229,200,0.28);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.1rem; flex-shrink: 0;
    }
    .brand-accent { color: var(--teal); }
    .brand-sub {
        font-family: var(--mono); font-size: 0.56rem;
        letter-spacing: 0.14em; text-transform: uppercase;
        color: var(--muted); margin-top: 1px;
    }
    .nav-right { display: flex; align-items: center; gap: 10px; }
    .nav-tag {
        font-family: var(--mono); font-size: 0.56rem;
        letter-spacing: 0.1em; text-transform: uppercase;
        padding: 5px 13px; border-radius: 100px;
        border: 1px solid var(--border); color: var(--muted);
    }
    .nav-tag-live {
        border-color: rgba(0,229,200,0.28); color: var(--teal);
        background: rgba(0,229,200,0.05);
    }
    @media(max-width:600px){.nav-right{display:none}}

    /* ── Ticker ── */
    .lp-ticker {
        border-bottom: 1px solid var(--border);
        background: var(--s1); overflow: hidden;
        padding: 9px 0; white-space: nowrap; position: relative;
    }
    .lp-ticker::before,.lp-ticker::after {
        content:''; position:absolute; top:0; bottom:0; width:100px; z-index:2;
    }
    .lp-ticker::before{left:0;background:linear-gradient(90deg,var(--s1),transparent)}
    .lp-ticker::after{right:0;background:linear-gradient(-90deg,var(--s1),transparent)}
    .ticker-track { display:inline-flex; animation:tickerScroll 40s linear infinite; }
    @keyframes tickerScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
    .t-item {
        font-family:var(--mono); font-size:0.56rem; color:var(--muted);
        letter-spacing:0.12em; padding:0 30px;
        display:inline-flex; align-items:center; gap:8px;
    }
    .t-dot{color:var(--teal);font-size:0.42rem}

    /* ── Hero ── */
    .lp-hero {
        max-width: 860px; margin: 0 auto;
        padding: clamp(56px,8vw,100px) clamp(20px,5vw,48px) clamp(48px,6vw,80px);
        text-align: center; display: flex; flex-direction: column; align-items: center;
    }
    .hero-eyebrow {
        display: inline-flex; align-items: center; gap: 8px;
        font-family: var(--mono); font-size: 0.6rem;
        letter-spacing: 0.2em; text-transform: uppercase; color: var(--teal);
        padding: 6px 16px; border-radius: 100px;
        border: 1px solid rgba(0,229,200,0.22);
        background: rgba(0,229,200,0.05); margin-bottom: 36px;
    }
    .hero-h1 {
        font-family: var(--display); font-weight: 800;
        font-size: clamp(2.8rem,7vw,5.4rem);
        line-height: 1.03; letter-spacing: -0.04em;
        color: var(--text); margin: 0 0 28px 0;
    }
    .hero-h1 em { font-style: normal; color: var(--teal); }
    .hero-h1 .h1-muted {
        display: block; font-size: clamp(1.6rem,3.8vw,2.8rem);
        color: var(--muted); font-weight: 600; letter-spacing: -0.025em; margin-top: 10px;
    }
    .hero-sub {
        font-family: var(--mono); font-size: clamp(0.78rem,1.5vw,0.92rem);
        color: var(--text2); line-height: 2; max-width: 620px; margin: 0 0 52px 0;
    }
    .hero-sub strong { color: var(--text); }

    /* ── Stat bar ── */
    .hero-stats {
        display: flex; justify-content: center; flex-wrap: wrap;
        gap: 0; border: 1px solid var(--border); border-radius: 16px;
        overflow: hidden; width: 100%; max-width: 600px;
        background: var(--s2);
    }
    .hs-block {
        flex: 1; min-width: 120px; padding: 20px 16px;
        text-align: center; border-right: 1px solid var(--border);
    }
    .hs-block:last-child{border-right:none}
    .hs-num {
        font-family: var(--display); font-weight: 800;
        font-size: 1.6rem; color: var(--teal); line-height: 1;
    }
    .hs-label {
        font-family: var(--mono); font-size: 0.52rem;
        color: var(--muted); text-transform: uppercase;
        letter-spacing: 0.14em; margin-top: 6px;
    }
    @media(max-width:480px){
        .hs-block{border-right:none;border-bottom:1px solid var(--border)}
        .hs-block:last-child{border-bottom:none}
    }

    /* ── Apps showcase ── */
    .apps-section {
        max-width: 1060px; margin: 0 auto;
        padding: clamp(32px,5vw,64px) clamp(20px,5vw,48px);
    }
    .section-head { text-align: center; margin-bottom: 44px; }
    .section-label {
        font-family: var(--mono); font-size: 0.56rem;
        letter-spacing: 0.22em; text-transform: uppercase; color: var(--muted);
        margin-bottom: 12px; display: block;
    }
    .section-title {
        font-family: var(--display); font-weight: 700;
        font-size: clamp(1.6rem,3.2vw,2.2rem); color: var(--text);
        letter-spacing: -0.03em; margin: 0;
    }
    .section-title em { font-style: normal; color: var(--teal); }

    .apps-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 18px;
    }
    @media(max-width:780px){.apps-grid{grid-template-columns:1fr;max-width:420px;margin:0 auto}}

    .app-card {
        background: var(--s2); border: 1px solid var(--border);
        border-radius: 20px; padding: 28px 24px;
        position: relative; overflow: hidden;
        transition: transform 0.25s, border-color 0.25s;
    }
    .app-card:hover { transform: translateY(-5px); border-color: var(--border2); }
    .app-card::after {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        opacity: 0; transition: opacity 0.3s;
    }
    .app-card:hover::after { opacity: 1; }
    .app-card.teal::after  { background: linear-gradient(90deg,transparent,var(--teal) 50%,transparent); }
    .app-card.purple::after{ background: linear-gradient(90deg,transparent,var(--purple) 50%,transparent); }
    .app-card.amber::after { background: linear-gradient(90deg,transparent,var(--amber) 50%,transparent); }

    .app-icon {
        width: 48px; height: 48px; border-radius: 13px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem; margin-bottom: 20px;
    }
    .app-icon.teal   { background: rgba(0,229,200,0.1); border: 1px solid rgba(0,229,200,0.2); }
    .app-icon.purple { background: rgba(124,109,240,0.1); border: 1px solid rgba(124,109,240,0.2); }
    .app-icon.amber  { background: rgba(245,166,35,0.1); border: 1px solid rgba(245,166,35,0.2); }

    .app-name {
        font-family: var(--display); font-weight: 700;
        font-size: 1.05rem; color: var(--text);
        letter-spacing: -0.02em; margin-bottom: 10px;
    }
    .app-desc {
        font-family: var(--mono); font-size: 0.68rem;
        color: var(--text2); line-height: 1.85; margin-bottom: 20px;
    }
    .app-tags {
        display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px;
    }
    .app-tag {
        font-family: var(--mono); font-size: 0.54rem;
        letter-spacing: 0.06em; text-transform: uppercase;
        padding: 4px 10px; border-radius: 6px;
        border: 1px solid var(--border); color: var(--muted);
    }

    /* ── Free trial section ── */
    .trial-section {
        max-width: 860px; margin: 0 auto;
        padding: clamp(20px,4vw,48px) clamp(20px,5vw,48px);
    }
    .trial-card {
        background: linear-gradient(135deg, rgba(0,229,200,0.055) 0%, rgba(124,109,240,0.06) 100%);
        border: 1px solid rgba(0,229,200,0.22); border-radius: 22px;
        padding: clamp(30px,4vw,48px) clamp(24px,4vw,48px);
        position: relative; overflow: hidden; text-align: center;
    }
    .trial-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg,transparent,var(--teal) 40%,var(--purple) 60%,transparent);
    }
    .trial-title {
        font-family: var(--display); font-weight: 800;
        font-size: clamp(1.5rem,3.2vw,2rem);
        color: var(--text); letter-spacing: -0.03em; margin-bottom: 12px;
    }
    .trial-title em { font-style: normal; color: var(--teal); }
    .trial-desc {
        font-family: var(--mono); font-size: 0.72rem;
        color: var(--text2); line-height: 2; margin-bottom: 28px;
        max-width: 540px; margin-left: auto; margin-right: auto;
    }
    .trial-limits {
        display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;
        margin-bottom: 32px;
    }
    .tl-pill {
        display: inline-flex; align-items: center; gap: 7px;
        font-family: var(--mono); font-size: 0.6rem; letter-spacing: 0.04em;
        padding: 7px 15px; border-radius: 8px;
        border: 1px solid var(--border2); background: var(--s2); color: var(--text2);
    }
    .tl-pill.ok  { border-color: rgba(0,229,200,0.25); color: var(--teal); }
    .tl-pill.no  { border-color: rgba(240,92,124,0.2); color: var(--pink); opacity: .85; }

    /* ── Pricing ── */
    .lp-pricing {
        max-width: 960px; margin: 0 auto;
        padding: clamp(32px,5vw,64px) clamp(20px,5vw,48px);
    }
    .pricing-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px;
    }
    @media(max-width:720px){.pricing-grid{grid-template-columns:1fr;max-width:380px;margin:0 auto}}

    .price-card {
        position: relative; background: var(--s2);
        border: 1px solid var(--border); border-radius: 20px;
        padding: 30px 26px 24px; transition: transform 0.25s, border-color 0.25s;
        overflow: hidden;
    }
    .price-card:hover{transform:translateY(-5px);border-color:var(--border2)}
    .price-card.featured{border-color:rgba(0,229,200,0.28);background:linear-gradient(155deg,rgba(0,229,200,0.035) 0%,rgba(124,109,240,0.04) 100%)}
    .price-card::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;opacity:0;transition:opacity 0.3s;background:linear-gradient(90deg,transparent,var(--teal) 50%,transparent)}
    .price-card.featured::after,.price-card:hover::after{opacity:1}

    .price-badge {
        position: absolute; top: 14px; right: 14px;
        font-family: var(--mono); font-size: 0.48rem;
        letter-spacing: 0.12em; text-transform: uppercase;
        padding: 4px 10px; border-radius: 100px;
    }
    .badge-pop{background:rgba(0,229,200,0.1);color:var(--teal);border:1px solid rgba(0,229,200,0.28)}
    .badge-val{background:rgba(124,109,240,0.1);color:var(--purple);border:1px solid rgba(124,109,240,0.28)}

    .price-plan{font-family:var(--mono);font-size:0.58rem;letter-spacing:0.18em;text-transform:uppercase;color:var(--muted);margin-bottom:14px}
    .price-amount{font-family:var(--display);font-weight:800;font-size:2.8rem;color:var(--text);line-height:1;letter-spacing:-0.03em}
    .price-curr{font-size:1.1rem;color:var(--muted);vertical-align:top;margin-top:9px;display:inline-block}
    .price-credits{font-family:var(--mono);font-size:0.68rem;color:var(--teal);margin:8px 0 20px}
    .price-note{font-family:var(--mono);font-size:0.58rem;color:var(--muted);margin-bottom:8px}
    .price-divider{height:1px;background:var(--border);margin-bottom:18px}
    .price-features{list-style:none;padding:0;margin:0 0 24px}
    .price-features li{font-family:var(--mono);font-size:0.62rem;color:var(--text2);padding:7px 0;display:flex;align-items:flex-start;gap:9px;border-bottom:1px solid rgba(255,255,255,0.03)}
    .price-features li:last-child{border-bottom:none}
    .pf-check{color:var(--teal);flex-shrink:0;margin-top:1px}
    .pf-x{color:var(--pink);flex-shrink:0;margin-top:1px}

    /* ── Pricing CTA link buttons ── */
    div[data-testid="column"]:nth-child(1) .stLinkButton a,
    div[data-testid="column"]:nth-child(3) .stLinkButton a {
        background: transparent !important; border: 1px solid var(--border2) !important;
        color: var(--text) !important; font-family: var(--display) !important;
        font-weight: 700 !important; font-size: 0.72rem !important;
        border-radius: 11px !important; padding: 12px 0 !important;
        width: 100% !important; display: block !important;
        text-align: center !important; letter-spacing: 0.04em !important;
        transition: border-color 0.2s, color 0.2s !important;
    }
    div[data-testid="column"]:nth-child(1) .stLinkButton a:hover,
    div[data-testid="column"]:nth-child(3) .stLinkButton a:hover {
        border-color: rgba(0,229,200,0.4) !important; color: var(--teal) !important;
    }
    div[data-testid="column"]:nth-child(2) .stLinkButton a {
        background: linear-gradient(135deg,#00e5c8,#00bfab) !important;
        border: none !important; color: #04090f !important;
        font-family: var(--display) !important; font-weight: 800 !important;
        font-size: 0.72rem !important; border-radius: 11px !important;
        padding: 12px 0 !important; width: 100% !important;
        display: block !important; text-align: center !important;
        letter-spacing: 0.04em !important;
        box-shadow: 0 4px 22px rgba(0,229,200,0.32) !important;
        transition: box-shadow 0.2s, transform 0.2s !important;
    }
    div[data-testid="column"]:nth-child(2) .stLinkButton a:hover {
        box-shadow: 0 7px 30px rgba(0,229,200,0.52) !important;
        transform: translateY(-2px) !important;
    }
    .stLinkButton{margin:0!important}

    /* ── Auth gate ── */
    .lp-gate {
        max-width: 560px; margin: 0 auto;
        padding: clamp(16px,3vw,36px) clamp(20px,5vw,48px) clamp(48px,7vw,80px);
    }
    .gate-card {
        background: var(--s2); border: 1px solid var(--border2);
        border-radius: 22px; padding: clamp(28px,5vw,46px) clamp(24px,5vw,46px);
        position: relative; overflow: hidden; text-align: center;
    }
    .gate-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg,transparent,var(--teal) 35%,var(--purple) 65%,transparent);
        opacity: .75;
    }
    .gate-lock {
        width: 54px; height: 54px; border-radius: 15px;
        background: linear-gradient(135deg,rgba(0,229,200,0.1),rgba(124,109,240,0.1));
        border: 1px solid rgba(0,229,200,0.2);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.5rem; margin: 0 auto 22px;
    }
    .gate-title {
        font-family: var(--display); font-weight: 800; font-size: 1.55rem;
        color: var(--text); letter-spacing: -0.028em; margin-bottom: 12px;
    }
    .gate-desc {
        font-family: var(--mono); font-size: 0.7rem;
        color: var(--text2); line-height: 1.9; margin-bottom: 28px;
    }
    .gate-desc strong { color: var(--text); }
    .key-format {
        display: inline-flex; align-items: center; gap: 8px;
        font-family: var(--mono); font-size: 0.6rem; color: var(--muted);
        background: rgba(255,255,255,0.025); border: 1px solid var(--border);
        border-radius: 8px; padding: 7px 16px; margin-bottom: 28px;
    }
    .kf-icon{color:var(--teal)}
    .gate-input-label {
        font-family: var(--mono); font-size: 0.56rem;
        text-transform: uppercase; letter-spacing: 0.16em;
        color: var(--muted); margin-bottom: 8px; display: block; text-align: left;
    }
    .gate-links {
        margin-top: 22px; text-align: center;
        font-family: var(--mono); font-size: 0.6rem;
        color: var(--muted); line-height: 2.4;
        display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 4px 2px;
    }
    .gate-links a{color:var(--teal);text-decoration:none}
    .gate-links a:hover{text-decoration:underline;text-underline-offset:2px}
    .gate-sep{color:var(--border2);margin:0 7px}
    .err-msg {
        margin-top: 12px; padding: 11px 16px;
        background: rgba(240,92,124,0.06); border: 1px solid rgba(240,92,124,0.22);
        border-radius: 10px; font-family: var(--mono); font-size: 0.66rem;
        color: var(--pink); display: flex; align-items: center; gap: 10px; text-align: left;
    }

    /* ── Input overrides (gate) ── */
    [data-testid="stTextInput"] > label { display:none !important }
    [data-testid="stTextInput"] > div > div > input {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.09) !important;
        border-radius: 12px !important; color: var(--text) !important;
        font-family: var(--mono) !important; font-size: 0.84rem !important;
        padding: 14px 18px !important; letter-spacing: 0.1em !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="stTextInput"] > div > div > input:focus {
        border-color: rgba(0,229,200,0.45) !important;
        box-shadow: 0 0 0 3px rgba(0,229,200,0.07) !important;
    }
    [data-testid="stTextInput"] > div > div > input::placeholder{color:#2c3450!important}
    [data-testid="baseButton-primary"] {
        background: linear-gradient(135deg,#00e5c8 0%,#00bfab 100%) !important;
        border: none !important; color: #04090f !important;
        font-family: var(--display) !important; font-weight: 800 !important;
        font-size: 0.86rem !important; letter-spacing: 0.04em !important;
        border-radius: 12px !important; padding: 14px !important;
        box-shadow: 0 4px 22px rgba(0,229,200,0.28) !important;
        transition: box-shadow 0.2s, transform 0.2s !important;
    }
    [data-testid="baseButton-primary"]:hover {
        box-shadow: 0 8px 32px rgba(0,229,200,0.48) !important;
        transform: translateY(-2px) !important;
    }
    /* Trial button */
    .trial-btn-zone .stButton > button {
        background: linear-gradient(135deg,#00e5c8,#00bfab) !important;
        border: none !important; color: #050b10 !important;
        font-family: var(--display) !important; font-weight: 800 !important;
        font-size: 0.84rem !important; border-radius: 13px !important;
        padding: 14px 40px !important; letter-spacing: 0.04em !important;
        box-shadow: 0 4px 24px rgba(0,229,200,0.3) !important;
        min-width: 260px;
    }
    .trial-btn-zone .stButton > button:hover {
        box-shadow: 0 8px 32px rgba(0,229,200,0.52) !important;
        transform: translateY(-2px) !important;
    }
    .trial-note{font-family:var(--mono);font-size:0.56rem;color:var(--muted);margin-top:12px;text-align:center}

    /* ── Footer ── */
    .lp-footer {
        border-top: 1px solid var(--border);
        padding: 22px clamp(20px,5vw,64px);
        display: flex; flex-wrap: wrap;
        justify-content: space-between; align-items: center; gap: 12px;
        background: rgba(5,7,15,0.94);
    }
    .footer-brand{font-family:var(--display);font-size:0.92rem;font-weight:800;color:var(--muted);letter-spacing:-0.02em}
    .footer-brand .ft{color:var(--teal)}
    .footer-links{display:flex;gap:24px;align-items:center}
    .footer-links a{font-family:var(--mono);font-size:0.56rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);text-decoration:none;transition:color .2s}
    .footer-links a:hover{color:var(--teal)}
    .footer-copy{font-family:var(--mono);font-size:0.52rem;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase;opacity:.45}
    @media(max-width:480px){.lp-footer{flex-direction:column;text-align:center}}

    /* ── App selector (post-auth) ── */
    .selector-wrap {
        max-width: 1020px; margin: 0 auto;
        padding: clamp(40px,6vw,80px) clamp(20px,5vw,48px);
    }
    .selector-header {
        margin-bottom: 48px; text-align: center;
    }
    .selector-greeting {
        font-family: var(--mono); font-size: 0.62rem;
        letter-spacing: 0.16em; text-transform: uppercase;
        color: var(--teal); margin-bottom: 14px; display: block;
    }
    .selector-title {
        font-family: var(--display); font-weight: 800;
        font-size: clamp(1.8rem,4vw,2.6rem); color: var(--text);
        letter-spacing: -0.03em; margin: 0 0 10px;
    }
    .selector-sub {
        font-family: var(--mono); font-size: 0.72rem;
        color: var(--text2); line-height: 1.8;
    }
    .selector-grid {
        display: grid; grid-template-columns: repeat(3,1fr); gap: 20px;
    }
    @media(max-width:780px){.selector-grid{grid-template-columns:1fr;max-width:420px;margin:0 auto}}

    .sel-card {
        background: var(--s2); border: 1px solid var(--border);
        border-radius: 20px; padding: 30px 26px;
        position: relative; overflow: hidden;
        transition: transform 0.25s, border-color 0.25s;
        cursor: pointer;
    }
    .sel-card:hover{transform:translateY(-6px)}
    .sel-card.teal:hover{border-color:rgba(0,229,200,0.35)}
    .sel-card.purple:hover{border-color:rgba(124,109,240,0.35)}
    .sel-card.amber:hover{border-color:rgba(245,166,35,0.35)}
    .sel-card::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;opacity:0;transition:opacity 0.3s}
    .sel-card:hover::after{opacity:1}
    .sel-card.teal::after{background:linear-gradient(90deg,transparent,var(--teal) 50%,transparent)}
    .sel-card.purple::after{background:linear-gradient(90deg,transparent,var(--purple) 50%,transparent)}
    .sel-card.amber::after{background:linear-gradient(90deg,transparent,var(--amber) 50%,transparent)}

    .sel-icon{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;margin-bottom:22px}
    .sel-icon.teal{background:rgba(0,229,200,0.1);border:1px solid rgba(0,229,200,0.22)}
    .sel-icon.purple{background:rgba(124,109,240,0.1);border:1px solid rgba(124,109,240,0.22)}
    .sel-icon.amber{background:rgba(245,166,35,0.1);border:1px solid rgba(245,166,35,0.22)}
    .sel-name{font-family:var(--display);font-weight:800;font-size:1.2rem;color:var(--text);letter-spacing:-0.025em;margin-bottom:10px}
    .sel-desc{font-family:var(--mono);font-size:0.68rem;color:var(--text2);line-height:1.9;margin-bottom:20px}
    .sel-features{list-style:none;padding:0;margin:0 0 24px}
    .sel-features li{font-family:var(--mono);font-size:0.6rem;color:var(--muted);padding:5px 0;display:flex;align-items:center;gap:8px;border-bottom:1px solid rgba(255,255,255,0.03)}
    .sel-features li:last-child{border-bottom:none}
    .sel-check-teal{color:var(--teal)}
    .sel-check-purple{color:var(--purple)}
    .sel-check-amber{color:var(--amber)}

    /* Selector CTA buttons */
    .sel-btn-teal .stButton > button{background:linear-gradient(135deg,rgba(0,229,200,0.12),rgba(0,229,200,0.06))!important;border:1px solid rgba(0,229,200,0.3)!important;color:var(--teal)!important;font-family:var(--display)!important;font-weight:700!important;border-radius:10px!important;transition:all .2s!important}
    .sel-btn-teal .stButton > button:hover{background:var(--teal)!important;color:#04090f!important;box-shadow:0 4px 20px rgba(0,229,200,0.3)!important}
    .sel-btn-purple .stButton > button{background:linear-gradient(135deg,rgba(124,109,240,0.12),rgba(124,109,240,0.06))!important;border:1px solid rgba(124,109,240,0.3)!important;color:var(--purple)!important;font-family:var(--display)!important;font-weight:700!important;border-radius:10px!important;transition:all .2s!important}
    .sel-btn-purple .stButton > button:hover{background:var(--purple)!important;color:#fff!important;box-shadow:0 4px 20px rgba(124,109,240,0.3)!important}
    .sel-btn-amber .stButton > button{background:linear-gradient(135deg,rgba(245,166,35,0.12),rgba(245,166,35,0.06))!important;border:1px solid rgba(245,166,35,0.3)!important;color:var(--amber)!important;font-family:var(--display)!important;font-weight:700!important;border-radius:10px!important;transition:all .2s!important}
    .sel-btn-amber .stButton > button:hover{background:var(--amber)!important;color:#04090f!important;box-shadow:0 4px 20px rgba(245,166,35,0.3)!important}

    /* Credit HUD (selector page) */
    .credit-hud {
        display: flex; align-items: center; justify-content: center;
        gap: 16px; margin-bottom: 48px; flex-wrap: wrap;
    }
    .credit-hud-pill {
        display: inline-flex; align-items: center; gap: 10px;
        background: var(--s2); border: 1px solid var(--border);
        border-radius: 100px; padding: 10px 20px;
        font-family: var(--mono); font-size: 0.68rem; color: var(--text2);
    }
    .credit-hud-pill .credit-num {
        font-family: var(--display); font-weight: 800; font-size: 1.2rem;
        color: var(--teal); line-height: 1;
    }
    .credit-hud-pill.warn .credit-num{color:var(--amber)}
    .credit-hud-pill.danger .credit-num{color:var(--pink)}

    /* Sign out button */
    .signout-zone .stButton > button{background:transparent!important;border:1px solid var(--border)!important;color:var(--muted)!important;font-family:var(--mono)!important;font-size:0.68rem!important;border-radius:8px!important;padding:7px 18px!important;transition:all .2s!important}
    .signout-zone .stButton > button:hover{border-color:var(--pink)!important;color:var(--pink)!important}
    </style>
    """, unsafe_allow_html=True)


    # ═══════════════════════════════════════════════════════════════════════════════
    # ROUTE: APP SELECTOR (authenticated)
    # ═══════════════════════════════════════════════════════════════════════════════

    if st.session_state.get("access_granted"):

        # Background layers
        st.markdown('<div class="lp-bg"></div><div class="lp-grid"></div>', unsafe_allow_html=True)

        credits_left   = st.session_state.get("user_credits", 0)
        trial_active   = is_trial()
        email_display  = st.session_state.get("user_email", "—")
        credit_display = "∞" if trial_active else str(credits_left)

        if trial_active:
            hud_class = ""
            credit_label = "Free Trial"
        elif credits_left > 5:
            hud_class = ""
            credit_label = "credits remaining"
        elif credits_left > 0:
            hud_class = "warn"
            credit_label = "credits remaining"
        else:
            hud_class = "danger"
            credit_label = "no credits"

        # Nav
        st.markdown(f"""
        <nav class="lp-nav fi d1">
            <div class="nav-brand">
                <div class="nav-logo">⬡</div>
                <div>
                    Bayant<span class="brand-accent">x360</span> Suite
                    <div class="brand-sub">Unified Analytics Platform</div>
                </div>
            </div>
            <div class="nav-right">
                <span class="nav-tag">{email_display}</span>
                <span class="nav-tag nav-tag-live"><span class="dot-live"></span>Session Active</span>
            </div>
        </nav>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="selector-wrap lp-wrap">
          <div class="selector-header fi d2">
            <span class="selector-greeting">⬡ Bayantx360 Suite — App Selector</span>
            <div class="selector-title">Which tool are you<br/>working with today?</div>
            <p class="selector-sub">
                Your single access key works across the entire suite.<br/>
                Credits are shared — usage is reflected in real time.
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Credit HUD
        st.markdown(f"""
        <div class="credit-hud fi d3">
            <div class="credit-hud-pill {hud_class}">
                <span class="credit-num">{credit_display}</span>
                <span>{credit_label}</span>
            </div>
            {'<div class="credit-hud-pill" style="border-color:rgba(240,92,124,0.2);color:var(--pink);font-size:0.6rem;">Trial: AI &amp; exports locked</div>' if trial_active else ''}
        </div>
        """, unsafe_allow_html=True)

        # App cards + launch buttons
        APPS = [
            {
                "name":     "PanelStatX",
                "icon":     "📐",
                "color":    "teal",
                "check":    "sel-check-teal",
                "btn":      "sel-btn-teal",
                "desc":     "Production-grade panel econometrics with Fixed Effects, Random Effects, and First-Difference estimators.",
                "features": ["OLS · FE · RE · First-Difference models", "Breusch-Pagan & Hausman tests", "Entity cross-section plots", "AI explainer (paid)", "DOCX report export (paid)"],
                "page_obj": st.session_state["_panelstatx_page"],
            },
            {
                "name":     "DataSynthX",
                "icon":     "🧬",
                "color":    "purple",
                "check":    "sel-check-purple",
                "btn":      "sel-btn-purple",
                "desc":     "Statistical synthetic data generation with full trust-metric validation and conformity scoring.",
                "features": ["Auto data profiling", "Synthetic generation engine", "Correlation & distribution fidelity", "AI trust analysis (paid)", "CSV / Excel export (paid)"],
                "page_obj": st.session_state["_datasynthx_page"],
            },
            {
                "name":     "EFActor",
                "icon":     "🔬",
                "color":    "amber",
                "check":    "sel-check-amber",
                "btn":      "sel-btn-amber",
                "desc":     "Psychometric analysis platform for Exploratory and Confirmatory Factor Analysis with auto-fix.",
                "features": ["KMO suitability & scree plot", "EFA with rotation (varimax etc.)", "CFA & fit indices", "Auto-fix problematic variables", "DOCX report export (paid)"],
                "page_obj": st.session_state["_efactor_page"],
            },
            
            {
                "name":     "DataCleanX",
                "icon":     "🧹",
                "color":    "teal",
                "check":    "sel-check-teal",
                "btn":      "sel-btn-teal",
                "desc":     "Automated data cleaning with smart profiling, missing-value imputation, outlier management, and a full audit log.",
                "features": ["Data Health Score (0–100)", "Auto-Clean mode", "Outlier visualisation & capping", "Column standardisation", "CSV / Excel + Audit Log export (paid)"],
                "page_obj": st.session_state["_datacleanx_page"],
            },
          
        ]

        cols = st.columns(4, gap="medium")

        for col, app in zip(cols, APPS):
            with col:
                features_html = "".join(
                    f'<li><span class="{app["check"]}">✓</span>{f}</li>'
                    for f in app["features"]
                )
                st.markdown(f"""
                <div class="sel-card {app['color']} fi d4">
                    <div class="sel-icon {app['color']}">{app['icon']}</div>
                    <div class="sel-name">{app['name']}</div>
                    <div class="sel-desc">{app['desc']}</div>
                    <ul class="sel-features">{features_html}</ul>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f'<div class="{app["btn"]}">', unsafe_allow_html=True)
                if st.button(
                    f"Launch {app['name']} →",
                    key=f"launch_{app['name']}",
                    type="primary",
                    use_container_width=True,
                ):
                    # Use StreamlitPage object — required for V2 callable-based routing.
                    # String paths don't resolve when the home page is a callable.
                    st.switch_page(app["page_obj"])
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)

        # Sign out
        _, so_col, _ = st.columns([3, 1, 3])
        with so_col:
            st.markdown('<div class="signout-zone">', unsafe_allow_html=True)
            if st.button("Sign Out", type="primary", use_container_width=True):
                sign_out()
            st.markdown("</div>", unsafe_allow_html=True)

        # Footer
        st.markdown("""
        <div class="lp-footer fi d8">
            <div class="footer-brand">Bayant<span class="ft">x360</span> Suite</div>
            <div class="footer-links">
                <a href="https://app.box.com/s/vw4c6u10bv0z8ngarzj73ej18t74e3wl" target="_blank">User Guide</a>
                <a href="mailto:bayantx360@gmail.com">Support</a>
            </div>
            <div class="footer-copy">Unified Analytics Platform · Credit-based access · No subscriptions</div>
        </div>
        """, unsafe_allow_html=True)

        st.stop()


    # ═══════════════════════════════════════════════════════════════════════════════
    # ROUTE: LANDING PAGE (unauthenticated)
    # ═══════════════════════════════════════════════════════════════════════════════

    # Background
    st.markdown('<div class="lp-bg"></div><div class="lp-grid"></div>', unsafe_allow_html=True)

    # Navbar
    st.markdown("""
    <nav class="lp-nav fi d1">
        <div class="nav-brand">
            <div class="nav-logo">⬡</div>
            <div>
                Bayant<span class="brand-accent">x360</span> Suite
                <div class="brand-sub">Unified Analytics Platform</div>
            </div>
        </div>
        <div class="nav-right">
            <span class="nav-tag">4+ Specialised Tools</span>
            <span class="nav-tag nav-tag-live"><span class="dot-live"></span>v2.0 Live</span>
        </div>
    </nav>
    """, unsafe_allow_html=True)

    # Ticker
    TICKER_ITEMS = [
        "Panel Data Econometrics", "Synthetic Data Generation", "Factor Analysis (EFA/CFA)",
        "Unified Access Key", "AI Explainer", "DOCX Report Export",
        "Breusch-Pagan Diagnostics", "Hausman Specification Test", "Trust Metric Validation",
        "Credit-Based Pay-As-You-Go", "No Monthly Subscription", "Instant Free Trial",
        "Auto-Fix Data Issues", "Varimax & Oblimin Rotation", "Correlation Preservation Score",
    ]
    ticker_html = "".join(
        f'<span class="t-item"><span class="t-dot">◆</span>{item}</span>'
        for item in TICKER_ITEMS
    )
    st.markdown(f"""
    <div class="lp-ticker fi d1">
        <div class="ticker-track">{ticker_html}{ticker_html}</div>
    </div>
    """, unsafe_allow_html=True)

    # Hero
    st.markdown("""
    <div class="lp-hero fi d2">

      <div class="hero-eyebrow">
        <span class="dot-live"></span>
        Bayantx360 Suite — Data. Impact. Intelligence.
      </div>

      <h1 class="hero-h1">
        Advanced Statistical
        <em>Analysis Suite</em>
        <span class="h1-muted">Built for researchers who mean business.</span>
      </h1>

      <p class="hero-sub">
        <strong>PanelStatX, DataSynthX, DataCleanX, EFActor</strong> — unified under a single access key
        with a shared credit balance. Run econometric models, generate synthetic data, and
        conduct psychometric analysis without switching platforms or managing separate accounts.
      </p>

      <div class="hero-stats">
        <div class="hs-block">
          <div class="hs-num">4+</div>
          <div class="hs-label">Specialised Tools</div>
        </div>
        <div class="hs-block">
          <div class="hs-num">1</div>
          <div class="hs-label">Access Key</div>
        </div>
        <div class="hs-block">
          <div class="hs-num">AI</div>
          <div class="hs-label">Intelligent Layer</div>
        </div>
        <div class="hs-block">
          <div class="hs-num">∞</div>
          <div class="hs-label">Free Trial</div>
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    # Apps showcase — st.html() bypasses the react-markdown / rehype-raw pipeline
    # entirely, rendering via DOMPurify directly. This avoids the lazy-load race
    # where rehype-raw hasn't mounted yet and raw HTML nodes fall back to escaped text.
    st.html("""
    <div class="apps-section fi d3">
      <div class="section-head">
        <span class="section-label">Why Bayantx360?</span>
        <div class="section-title">
          Why Researchers, Students & Data Analysts are choosing<br><em>Bayantx360 Suite.</em>
        </div>
      </div>
      <div class="apps-grid">

        <div class="app-card teal">
          <div class="app-icon teal">⚡️</div>
          <div class="app-name">No Code</div>
          <div class="app-desc">
            Run advanced statistical analysis through an intuitive interface — without writing syntax, configuring environments, or learning complex software.
          </div>
          <div class="app-tags">
            <span class="app-tag">No Code</span>
            <span class="app-tag">No Syntax</span>
            <span class="app-tag">Research-Friendly</span>
          </div>
        </div>

        <div class="app-card purple">
          <div class="app-icon purple">🚀</div>
          <div class="app-name">Ready in Seconds</div>
          <div class="app-desc">
            No installs, no dependencies, no setup. Open your browser. 
            Eenter your key, and run production-grade statistical models from any device.
          </div>
          <div class="app-tags">
            <span class="app-tag">Zero Setup</span>
            <span class="app-tag">Cross-Platform</span>
            <span class="app-tag">Browser-Native</span>
          </div>
        </div>

        <div class="app-card amber">
          <div class="app-icon amber">💳</div>
          <div class="app-name">License Fee-Free</div>
          <div class="app-desc">
            Skip costly annual subscriptions and restrictive academic licenses.
            Access and use advanced statistical tools for free anytime. Only pay for exporting valuable data and results through a flexible credit-based,pay-as-you-go model.
          </div>
          <div class="app-tags">
            <span class="app-tag">No Monthly Subscription</span>
            <span class="app-tag">Credit-based</span>
            <span class="app-tag">Pay-As-You-Go</span>
          </div>
        </div>

      </div>
    </div>
    """)

    # Free Trial section
    st.markdown("""
    <div class="trial-section fi d4">
      <div class="trial-card">
        <span style="font-family:var(--mono);font-size:0.58rem;letter-spacing:0.22em;text-transform:uppercase;color:var(--teal);margin-bottom:14px;display:block;">
            ⬡ No credit card · No sign-up · Instant access
        </span>
        <div class="trial-title">Try the <em>Suite</em> Free</div>
        <p class="trial-desc">
            All three tools. Full analysis. Zero cost.<br/>
            Upgrade a paid plan when you need to export results or unlock AI interpretation.
        </p>
        <div class="trial-limits">
          <span class="tl-pill ok">✓ All analysis features</span>
          <span class="tl-pill ok">✓ Upload any dataset</span>
          <span class="tl-pill ok">✓ Full results &amp; diagnostics</span>
          <span class="tl-pill ok">✓ Charts &amp; entity plots</span>
          <span class="tl-pill no">✗ AI Explainer (paid)</span>
          <span class="tl-pill no">✗ Export: DOCX / CSV / Excel (paid)</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, trial_col, _ = st.columns([1.6, 1, 1.6])
    with trial_col:
        st.markdown('<div class="trial-btn-zone">', unsafe_allow_html=True)
        free_trial_btn = st.button(
            "⬡  Use Free Version",
            type="primary",
            key="free_trial_btn",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="trial-note">No sign-up · No credit card · All 3 tools included</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Pricing
    st.markdown("""
    <div class="lp-pricing fi d5">
      <div class="section-head">
        <div class="section-title">Buy Credits & <em>Access More</em> Features</div>
        <span class="section-label">Pay-as-you-go credits · No monthly subscription · Credits never expire</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    pc1, pc2, pc3 = st.columns(3, gap="small")

    with pc1:
        st.markdown("""
        <div class="price-card fi d3">
          <div class="price-plan">Starter</div>
          <div class="price-amount"><span class="price-curr">.</span>$8</div>
          <div class="price-credits">5 Suite Credits</div>
          <div class="price-note">Works across all apps</div>
          <div class="price-divider"></div>
          <ul class="price-features">
            <li><span class="pf-check">✓</span>Unlimited analysis runs across any app</li>
            <li><span class="pf-check">✓</span>AI explainer unlocked</li>
            <li><span class="pf-check">✓</span>All export formats (DOCX, CSV, Excel)</li>
            <li><span class="pf-check">✓</span>Credits never expire</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)
        st.link_button("Buy Credits →", "https://flutterwave.com/pay/tumvwsar2zi5", type="primary", use_container_width=True)

    with pc2:
        st.markdown("""
        <div class="price-card featured fi d4">
          <span class="price-badge badge-pop">Most Popular</span>
          <div class="price-plan">Standard</div>
          <div class="price-amount"><span class="price-curr">.</span>$18</div>
          <div class="price-credits">15 Suite Credits</div>
          <div class="price-note">Best value for active researchers</div>
          <div class="price-divider"></div>
          <ul class="price-features">
            <li><span class="pf-check">✓</span>Unlimited analysis runs across any app</li>
            <li><span class="pf-check">✓</span>AI explainer unlocked</li>
            <li><span class="pf-check">✓</span>All export formats (DOCX, CSV, Excel)</li>
            <li><span class="pf-check">✓</span>Credits never expire</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)
        st.link_button("Buy Credits →", "https://flutterwave.com/pay/w08ixsaspudw", type="primary", use_container_width=True)

    with pc3:
        st.markdown("""
        <div class="price-card fi d5">
          <span class="price-badge badge-val">Best Value</span>
          <div class="price-plan">Pro</div>
          <div class="price-amount"><span class="price-curr">.</span>$30</div>
          <div class="price-credits">30 Suite Credits</div>
          <div class="price-note">For teams and power researchers</div>
          <div class="price-divider"></div>
          <ul class="price-features">
            <li><span class="pf-check">✓</span>Unlimited analysis runs across any app</li>
            <li><span class="pf-check">✓</span>AI explainer unlocked</li>
            <li><span class="pf-check">✓</span>All export formats (DOCX, CSV, Excel)</li>
            <li><span class="pf-check">✓</span>Credits never expire</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)
        st.link_button("Buy Credits →", "https://flutterwave.com/pay/rjsshar0wqlk", type="primary", use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Auth Gate
    st.markdown("""
    <div class="lp-gate fi d6">
      <div class="gate-card">
        <div class="gate-lock">🔑</div>
        <div class="gate-title">Enter Your Access Key</div>
        <div class="gate-desc">
          The Bayantx360 Suite uses a <strong>credit-based, pay-as-you-go model</strong>.
          One key unlocks <strong>all three tools</strong> with a shared credit balance
          that updates in real time. No recurring billing. Credits never expire.
        </div>
        <div class="key-format">
            <span class="kf-icon">◈</span>
            Key format:&nbsp; BTX-XXXX-XXXX-XXXX
        </div>
        <div class="gate-form">
            <span class="gate-input-label">Access Key</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, gate_col, _ = st.columns([1, 2, 1])
    with gate_col:
        entered_key = st.text_input(
            "Access Key",
            type="password",
            placeholder="BTX-XXXX-XXXX-XXXX",
            label_visibility="collapsed",
            key="suite_key_input",
        )
        unlock_btn = st.button(
            "⬡  Unlock the Suite",
            use_container_width=True,
            type="primary",
            key="unlock_btn",
        )

        if st.session_state.get("access_error"):
            st.markdown(f"""
            <div class="err-msg">
                <span>✕</span> {st.session_state.access_error}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div class="gate-links">
            <a href="https://x.com/bayantx360" target="_blank">👤 Contact Sales</a>
            <span class="gate-sep">|</span>
            <a href="https://app.box.com/s/vw4c6u10bv0z8ngarzj73ej18t74e3wl" target="_blank">📋 User Guide</a>
            <span class="gate-sep">|</span>
            <a href="mailto:bayantx360@gmail.com">⚙ Support</a>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div class="lp-footer fi d8">
        <div class="footer-brand">Bayant<span class="ft">x360</span> Suite</div>
        <div class="footer-links">
            <a href="https://x.com/bayantx360" target="_blank">Twitter / X</a>
            <a href="https://app.box.com/s/vw4c6u10bv0z8ngarzj73ej18t74e3wl" target="_blank">User Guide</a>
            <a href="mailto:bayantx360@gmail.com">Support</a>
        </div>
        <div class="footer-copy">Bayantx360 · Unified Analytics Suite · Credit-based access</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Button handlers ────────────────────────────────────────────────────────────
    if free_trial_btn:
        activate_free_trial()

    if unlock_btn:
        process_key_login(entered_key)


# ── V2 Router setup ───────────────────────────────────────────────────────────
# st.navigation() MUST come before st.set_page_config() — it is the first
# Streamlit call. _pg.run() dispatches to the current page's callable/file.
_home_page      = st.Page(render_home,            title="Bayantx360 Suite", icon="🌐", default=True)
_panelstatx_page = st.Page("pages/panelstatx.py",  title="PanelStatX",       icon="📐")
_datasynthx_page = st.Page("pages/datasynthx.py",  title="DataSynthX",       icon="🧬")
_efactor_page    = st.Page("pages/efactor.py",     title="EFActor",          icon="🔬")
_datacleanx_page    = st.Page("pages/datacleanx.py",     title="DataCleanX",          icon="🧹")
 
_pg = st.navigation(
    [_home_page, _panelstatx_page, _datasynthx_page, _efactor_page, _datacleanx_page],
    position="hidden",
)

st.set_page_config(
    page_title="Bayantx360 Suite",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Store page objects in session so sub-pages can switch back to home
# without using "suite_home.py" string path (invalid for callable pages).
st.session_state["_home_page"]       = _home_page
st.session_state["_panelstatx_page"] = _panelstatx_page
st.session_state["_datasynthx_page"] = _datasynthx_page
st.session_state["_efactor_page"]    = _efactor_page
st.session_state["_datacleanx_page"]    = _datacleanx_page

_pg.run()
