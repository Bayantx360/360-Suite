"""
pages/testimonials.py
══════════════════════════════════════════════════════════════════════
StaX360 Suite — Public Testimonials Page
══════════════════════════════════════════════════════════════════════

Public marketing page — no auth required. Mirrors the pattern used in
BizTrack-OS's suite_home.py::page_testimonials(), adapted to StaX360's
dark/teal design system (DM Mono + Bricolage Grotesque, --teal #00e5c8).

To add / update testimonials: edit the TESTIMONIALS list below.
No database involved — everything here is static content.

Photos: drop files into assets/avatars/ and reference the filename.
If a photo is missing, the avatar falls back to initials automatically.
"""

import base64
import os
import sys

import streamlit as st

# ── Path resolution so `shared` is importable ─────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.auth import init_session_state

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Testimonials · StaX360 Suite",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_session_state()


# ══════════════════════════════════════════════════════════════════════════════
# EDIT THIS LIST to add / update testimonials — no DB involved
# ══════════════════════════════════════════════════════════════════════════════
TESTIMONIALS = [
    {
        "name": "PLACEHOLDER — replace with real user/institution",
        "person": "PLACEHOLDER — Name (Role)",
        "photo": "user1.jpeg",
        "rating": 5,
        "comment": "PLACEHOLDER — swap in an actual quote from a StaX360 user "
                   "describing how PanelStatX, DataSynthX, DataCleanX or EFActor "
                   "helped their research or analysis.",
    },
    {
        "name": "PLACEHOLDER — replace with real user/institution",
        "person": "PLACEHOLDER — Name (Role)",
        "photo": "user2.jpeg",
        "rating": 5,
        "comment": "PLACEHOLDER — swap in an actual quote here.",
    },
    {
        "name": "PLACEHOLDER — replace with real user/institution",
        "person": "PLACEHOLDER — Name (Role)",
        "photo": "user3.jpeg",
        "rating": 5,
        "comment": "PLACEHOLDER — swap in an actual quote here.",
    },
    {
        "name": "PLACEHOLDER — replace with real user/institution",
        "person": "PLACEHOLDER — Name (Role)",
        "photo": "user4.jpeg",
        "rating": 5,
        "comment": "PLACEHOLDER — swap in an actual quote here.",
    },
]


def _avatar_html(filename: str, name: str, size: int = 44) -> str:
    """Circular avatar from assets/avatars/<filename>, falling back to initials."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "avatars", filename,
    )
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = filename.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'border:2px solid #05070f;flex-shrink:0;overflow:hidden;">'
            f'<img src="data:{mime};base64,{b64}" '
            f'style="width:100%;height:100%;object-fit:cover;display:block;"/>'
            f'</div>'
        )
    except Exception:
        initials = "".join(p[0].upper() for p in name.split()[:2]) or "?"
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:#10141f;border:2px solid #05070f;flex-shrink:0;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-family:\'DM Mono\',monospace;font-size:13px;font-weight:600;'
            f'color:#00e5c8;">{initials}</div>'
        )


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500&family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #0a0c10 !important;
    color: #e4eaf8 !important;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"], footer, #MainMenu, [data-testid="stToolbar"] {
    display: none !important;
}
[data-testid="stHeader"], [data-testid="stDecoration"] {
    background: #0a0c10 !important; background-color: #0a0c10 !important;
}
[data-testid="block-container"] { padding: 2rem 1rem 3rem !important; max-width: 100% !important; }

.tm-header { text-align:center; padding: 18px 0 26px; }
.tm-eyebrow {
  display:inline-flex; align-items:center; gap:7px;
  font-family:'DM Mono',monospace; font-size:0.65rem; letter-spacing:0.1em;
  text-transform:uppercase; color:#00e5c8;
  border:1px solid rgba(0,229,200,0.28); background:rgba(0,229,200,0.05);
  padding:5px 13px; border-radius:100px; margin-bottom:14px;
}
.tm-title {
  font-family:'Bricolage Grotesque',sans-serif; font-size:2rem; font-weight:800;
  color:#e4eaf8; letter-spacing:-0.03em;
}
.tm-sub {
  font-family:'DM Mono',monospace; font-size:0.85rem; color:#9aa3be;
  margin-top:0.6rem; max-width:480px; margin-left:auto; margin-right:auto;
  line-height:1.6;
}
.tm-card {
  background:#10141f; border:1px solid rgba(255,255,255,0.06);
  border-radius:14px; padding:18px 20px; margin-bottom:14px;
}
.tm-card-head { display:flex; align-items:center; gap:14px; margin-bottom:10px; }
.tm-card-name { font-family:'Bricolage Grotesque',sans-serif; font-weight:700; color:#e4eaf8; font-size:0.92rem; }
.tm-card-person { font-family:'DM Mono',monospace; font-size:0.72rem; color:#9aa3be; }
.tm-stars { color:#f5a623; font-size:0.82rem; letter-spacing:2px; margin-top:2px; }
.tm-comment { font-family:'DM Mono',monospace; font-size:0.85rem; color:#c7ceE0; line-height:1.6; }
</style>

<div class="tm-header">
  <div class="tm-eyebrow">⭐ Social proof</div>
  <div class="tm-title">What our users are saying</div>
  <div class="tm-sub">
    Real feedback from researchers and analysts using StaX360 to run
    panel data models, synthesize data, and factor-analyze results —
    without paying for licensed statistical software.
  </div>
</div>
""", unsafe_allow_html=True)

_, col, _ = st.columns([1, 1.6, 1])
with col:
    for t in TESTIMONIALS:
        stars = "★" * t["rating"] + "☆" * (5 - t["rating"])
        st.markdown(f"""
<div class="tm-card">
  <div class="tm-card-head">
    {_avatar_html(t["photo"], t["person"], size=44)}
    <div>
      <div class="tm-card-name">{t["name"]}</div>
      <div class="tm-card-person">{t["person"]}</div>
      <div class="tm-stars">{stars}</div>
    </div>
  </div>
  <div class="tm-comment">{t["comment"]}</div>
</div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("← Back to home", use_container_width=True):
            st.switch_page(st.session_state["_home_page"])
    with bc2:
        if st.button("⬡ Use Free Version", use_container_width=True, type="primary"):
            st.session_state["_goto"] = st.session_state["_home_page"]
            st.session_state["_scroll_to_trial"] = True
            st.switch_page(st.session_state["_home_page"])
