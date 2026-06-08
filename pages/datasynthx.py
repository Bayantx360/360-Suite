"""
apps/datasynthx.py
══════════════════════════════════════════════════════════════════════
Bayantx360 Suite — DataSynthX
Synthetic Data Generation Platform
══════════════════════════════════════════════════════════════════════

Changes from standalone version (app__27_.py):
  • Auth + credit engine → shared/auth.py
  • CSS → shared/theme.py  (suite-unified visual system)
  • Single secret: BAYANTX_SHEET_ID
  • Trial gate: is_free_trial flag (no row-gen for trial; export locked)
  • Credit deduction → handle_credit_deduction() from shared.auth
  • Back-to-suite navigation in sidebar
  • Trial row cap preserved: export locked entirely (not 70-row workaround)

All statistical logic (DataProfiler, SyntheticDataGenerator, TrustMetrics,
SCI, KS/Wasserstein/KL, AI explainer, Excel export) 100% preserved.
"""

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
from scipy.stats import ks_2samp, wasserstein_distance
from openai import OpenAI
import plotly.graph_objects as go
import io
import warnings
import sys, os
warnings.filterwarnings("ignore")


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.auth import (
    init_session_state,
    refresh_credits,
    handle_credit_deduction,
    render_credit_hud,
    can_use_premium,
    is_trial,
    sign_out,
)
from shared.theme import apply_suite_css, apply_theme, render_locked_banner

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DataSynthX · Bayantx360 Suite",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
apply_suite_css()

if not st.session_state.get("access_granted"):
    st.switch_page(st.session_state["_home_page"])
    st.stop()

refresh_credits()

# Per-app session keys
for key, default in [
    ("synth_df", None), ("trust_metrics", None),
    ("gen_status", None), ("ai_explanation", ""),
    ("ai_use_case_saved", ""),
    ("uploaded_file_bytes", None), ("uploaded_file_name", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ═══════════════════════════════════════════════════════════════════════════════
# CORE ENGINES  (100% preserved from original)
# ═══════════════════════════════════════════════════════════════════════════════

class DataProfiler:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
        self.datetime_cols = []
        for col in self.categorical_cols[:]:
            try:
                parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
                if parsed.notna().sum() > len(df) * 0.7:
                    self.datetime_cols.append(col)
                    self.categorical_cols.remove(col)
            except Exception:
                pass

    def profile(self) -> dict:
        p = {}
        p["numeric_stats"] = {}
        for col in self.numeric_cols:
            s = self.df[col].dropna()
            p["numeric_stats"][col] = {
                "mean": float(s.mean()), "std": float(s.std()),
                "variance": float(s.var()), "min": float(s.min()),
                "max": float(s.max()), "skew": float(s.skew()),
                "kurtosis": float(s.kurtosis()),
                "missing_ratio": float(self.df[col].isna().mean()),
                "values": s.values,
            }
        p["categorical_stats"] = {}
        for col in self.categorical_cols:
            s = self.df[col].dropna()
            freq = s.value_counts(normalize=True)
            p["categorical_stats"][col] = {
                "frequencies": freq.to_dict(), "n_unique": int(s.nunique()),
                "missing_ratio": float(self.df[col].isna().mean()),
                "mode": str(s.mode().iloc[0]) if len(s) > 0 else None,
            }
        if len(self.numeric_cols) >= 2:
            p["correlation_matrix"] = self.df[self.numeric_cols].corr().fillna(0)
        else:
            p["correlation_matrix"] = pd.DataFrame()
        p["shape"] = self.df.shape
        p["numeric_cols"] = self.numeric_cols
        p["categorical_cols"] = self.categorical_cols
        p["datetime_cols"] = self.datetime_cols
        p["missing_overview"] = self.df.isna().mean().to_dict()
        return p


class SyntheticDataGenerator:
    def __init__(self, df: pd.DataFrame, profile: dict):
        self.df = df
        self.profile = profile
        self.numeric_cols = profile["numeric_cols"]
        self.categorical_cols = profile["categorical_cols"]

    def generate(self, n_rows: int, noise_level: float = 0.02) -> pd.DataFrame:
        synthetic = {}
        if self.numeric_cols:
            clean = self.df[self.numeric_cols].dropna()
            n_num = len(self.numeric_cols)
            if len(clean) >= 2:
                mean_vec = clean.mean().fillna(0).values
                cov_matrix = clean.cov().fillna(0).values.copy()
                cov_matrix = np.atleast_2d(cov_matrix).reshape(n_num, n_num)
                cov_matrix += np.eye(n_num) * 1e-8
                try:
                    samples = np.random.multivariate_normal(mean_vec, cov_matrix, n_rows)
                except (np.linalg.LinAlgError, ValueError):
                    samples = np.column_stack([
                        np.random.normal(
                            self.profile["numeric_stats"][c]["mean"],
                            max(self.profile["numeric_stats"][c]["std"], 1e-6),
                            n_rows,
                        ) for c in self.numeric_cols
                    ])
                samples = np.atleast_2d(samples).reshape(n_rows, n_num)
                noise = np.random.normal(0, noise_level, samples.shape)
                noise *= np.std(samples, axis=0, keepdims=True)
                samples += noise
                for i, col in enumerate(self.numeric_cols):
                    s = self.profile["numeric_stats"][col]
                    col_range = s["max"] - s["min"]
                    lo, hi = s["min"] - col_range * 0.05, s["max"] + col_range * 0.05
                    samples[:, i] = np.clip(samples[:, i], lo, hi)
                    if np.issubdtype(self.df[col].dtype, np.integer):
                        synthetic[col] = np.round(samples[:, i]).astype(int)
                    else:
                        synthetic[col] = samples[:, i]
            else:
                for col in self.numeric_cols:
                    s = self.profile["numeric_stats"][col]
                    synthetic[col] = np.random.normal(s["mean"], max(s["std"], 1e-6), n_rows)

        for col in self.categorical_cols:
            cat_stats = self.profile["categorical_stats"][col]
            categories = list(cat_stats["frequencies"].keys())
            probs = np.array(list(cat_stats["frequencies"].values()), dtype=float)
            probs /= probs.sum()
            synthetic[col] = np.random.choice(categories, size=n_rows, p=probs)

        for col in self.numeric_cols + self.categorical_cols:
            missing_ratio = self.profile["missing_overview"].get(col, 0)
            if missing_ratio > 0:
                mask = np.random.rand(n_rows) < missing_ratio
                s = pd.Series(synthetic[col])
                s[mask] = np.nan
                synthetic[col] = s.values

        synth_df = pd.DataFrame(synthetic)
        orig_cols = [c for c in self.df.columns if c in synth_df.columns]
        return synth_df[orig_cols]


class TrustMetrics:
    def __init__(self, original: pd.DataFrame, synthetic: pd.DataFrame, profile: dict):
        self.orig = original
        self.synth = synthetic
        self.profile = profile
        self.numeric_cols = profile["numeric_cols"]
        self.categorical_cols = profile["categorical_cols"]

    def correlation_preservation_score(self):
        if len(self.numeric_cols) < 2:
            return 1.0, pd.DataFrame(), pd.DataFrame()
        orig_corr = self.orig[self.numeric_cols].corr().fillna(0)
        synth_corr = self.synth[self.numeric_cols].corr().fillna(0)
        diff = np.abs(orig_corr.values - synth_corr.values)
        return float(max(0.0, 1.0 - diff.mean())), orig_corr, synth_corr

    def distribution_similarity_scores(self) -> dict:
        scores = {}
        for col in self.numeric_cols:
            a = self.orig[col].dropna().values
            b = self.synth[col].dropna().values
            if len(a) < 2 or len(b) < 2:
                scores[col] = {"ks_stat": 0, "ks_pvalue": 1, "wasserstein": 0, "score": 1.0}
                continue
            ks_stat, ks_p = ks_2samp(a, b)
            w_dist = wasserstein_distance(a, b) / (np.std(a) + 1e-9)
            scores[col] = {
                "ks_stat": float(ks_stat), "ks_pvalue": float(ks_p),
                "wasserstein": float(w_dist), "score": float(max(0.0, 1.0 - ks_stat)),
            }
        return scores

    def categorical_fidelity_scores(self) -> dict:
        scores = {}
        for col in self.categorical_cols:
            orig_freq = self.orig[col].value_counts(normalize=True)
            synth_freq = self.synth[col].value_counts(normalize=True)
            all_cats = set(orig_freq.index) | set(synth_freq.index)
            p = np.array([orig_freq.get(c, 1e-10) for c in all_cats])
            q = np.array([synth_freq.get(c, 1e-10) for c in all_cats])
            p /= p.sum(); q /= q.sum()
            kl_div = float(min(np.sum(p * np.log((p + 1e-10) / (q + 1e-10))), 10.0))
            scores[col] = {
                "kl_divergence": kl_div, "score": float(max(0.0, 1.0 - kl_div / 10.0)),
                "orig_freq": orig_freq.to_dict(), "synth_freq": synth_freq.to_dict(),
            }
        return scores

    def compute_sci(self) -> dict:
        corr_score, orig_corr, synth_corr = self.correlation_preservation_score()
        dist_scores = self.distribution_similarity_scores()
        cat_scores  = self.categorical_fidelity_scores()
        avg_dist = np.mean([v["score"] for v in dist_scores.values()]) if dist_scores else 1.0
        avg_cat  = np.mean([v["score"] for v in cat_scores.values()])  if cat_scores  else 1.0
        w_corr, w_dist, w_cat = 0.30, 0.40, 0.30
        if not dist_scores: w_corr, w_dist, w_cat = 0.40, 0.0, 0.60
        if not cat_scores:  w_corr, w_dist, w_cat = 0.35, 0.65, 0.0
        if not dist_scores and not cat_scores: w_corr, w_dist, w_cat = 1.0, 0.0, 0.0
        sci = round((w_corr * corr_score + w_dist * avg_dist + w_cat * avg_cat) * 100, 1)
        return {
            "sci": sci,
            "correlation_score": round(corr_score * 100, 1),
            "distribution_score": round(avg_dist * 100, 1),
            "categorical_score": round(avg_cat * 100, 1),
            "orig_corr": orig_corr, "synth_corr": synth_corr,
            "dist_scores": dist_scores, "cat_scores": cat_scores,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────
def score_color(score: float) -> str:
    if score >= 85: return "#00e5c8"
    if score >= 65: return "#7c6df0"
    return "#f05c7c"

def score_badge(score: float):
    if score >= 85: return "badge-teal",   "EXCELLENT"
    if score >= 65: return "badge-purple", "GOOD"
    return "badge-red", "NEEDS REVIEW"

def download_credit_cost(n_rows: int) -> int:
    if n_rows < 100:   return 0
    if n_rows <= 500:  return 1
    if n_rows <= 1000: return 2
    return 5

def render_heatmap(corr_df: pd.DataFrame, title: str):
    MAX_COLS = 30
    cols = list(corr_df.columns)
    n_total = len(cols)
    if n_total == 0:
        st.caption("Not enough numeric columns for correlation.")
        return
    truncated = n_total > MAX_COLS
    cols = cols[:MAX_COLS]
    corr_df = corr_df.loc[cols, cols]
    n = len(cols)
    colorscale = [[0.0, "rgb(240,92,124)"], [0.5, "rgb(17,19,24)"], [1.0, "rgb(0,229,200)"]]
    fig = go.Figure(go.Heatmap(
        z=corr_df.values.tolist(), x=list(cols), y=list(cols),
        text=[[f"{v:.2f}" for v in row] for row in corr_df.values] if n <= 20 else None,
        texttemplate="%{text}" if n <= 20 else None,
        textfont={"size": max(7, 11 - n // 4), "color": "white"},
        colorscale=colorscale, zmin=-1, zmax=1, showscale=True,
        colorbar=dict(thickness=12, len=0.8, tickfont=dict(color="#6b7a9a", size=9),
                      tickvals=[-1, -0.5, 0, 0.5, 1], outlinewidth=0),
        hovertemplate="%{y} × %{x}<br>r = %{z:.3f}<extra></extra>",
    ))
    chart_px = max(300, min(520, 30 * n + 80))
    fig.update_layout(
        title=dict(text=title, font=dict(family="DM Mono, monospace", size=10, color="#6b7a9a"),
                   x=0, xanchor="left", pad=dict(b=12)),
        paper_bgcolor="#111318", plot_bgcolor="#111318",
        margin=dict(l=10, r=10, t=40, b=10), height=chart_px,
        xaxis=dict(tickfont=dict(size=max(7, 10 - n // 6), color="#9aa3be",
                                  family="DM Mono, monospace"),
                   tickangle=-45, showgrid=False, zeroline=False),
        yaxis=dict(tickfont=dict(size=max(7, 10 - n // 6), color="#9aa3be",
                                  family="DM Mono, monospace"),
                   showgrid=False, zeroline=False, autorange="reversed"),
        font=dict(color="#e2e8f4"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if truncated:
        st.caption(f"Showing first {MAX_COLS} of {n_total} columns.")

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="SyntheticData")
        wb = writer.book
        ws = writer.sheets["SyntheticData"]
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#181c24",
                                  "font_color": "#00e5c8", "border": 1})
        for ci, col in enumerate(df.columns):
            ws.write(0, ci, col, hdr_fmt)
            ws.set_column(ci, ci, max(12, len(str(col)) + 4))
    return buf.getvalue()

@st.cache_data
def load_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    name = file_name.lower()
    buf = io.BytesIO(file_bytes)
    if name.endswith(".csv"):
        try:
            return pd.read_csv(buf)
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
    elif name.endswith(".xlsx"):
        return pd.read_excel(buf, engine="openpyxl")
    elif name.endswith(".xls"):
        return pd.read_excel(buf, engine="xlrd")
    raise ValueError(f"Unsupported file type: {file_name}")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="padding:14px 0 20px 0;border-bottom:1px solid var(--border);margin-bottom:18px;">
        <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;
                    color:var(--text);letter-spacing:-0.02em;">
            🧬 Data<span style="color:var(--accent2);">Synth</span>X
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);
                    margin-top:4px;letter-spacing:0.08em;">
            SYNTHETIC DATA PLATFORM · BAYANTX360 SUITE
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_credit_hud()

    if st.button("⬡ Back to Suite", use_container_width=True):
        st.switch_page(st.session_state["_home_page"])

    st.markdown("---")
    st.markdown('<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.12em;color:var(--muted);margin-bottom:10px;">Upload Dataset</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "CSV or Excel", type=["csv", "xlsx", "xls"],
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        if file_bytes:
            st.session_state.uploaded_file_bytes = file_bytes
            st.session_state.uploaded_file_name  = uploaded_file.name

    st.markdown("---")
    st.markdown('<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.12em;color:var(--muted);margin-bottom:10px;">Generation Config</div>', unsafe_allow_html=True)

    n_rows = st.number_input(
        "Target rows to generate", min_value=10, max_value=1_000_000,
        value=1000, step=100,
    )
    noise_level = st.slider(
        "Noise level", min_value=0.0, max_value=0.20, value=0.02, step=0.01,
        help="Gaussian noise added to numeric columns (fraction of std)",
    )

    st.markdown("---")
    generate_btn = st.button("🧬 Generate Synthetic Data", type="primary", use_container_width=True)

    gen_status = st.session_state.get("gen_status")
    if gen_status == "done":
        sci_val = st.session_state.get("trust_metrics", {}).get("sci", "—")
        n_synth = len(st.session_state["synth_df"]) if st.session_state.get("synth_df") is not None else 0
        st.markdown(f"""
        <div style="background:rgba(0,229,200,0.06);border:1px solid rgba(0,229,200,0.22);
                    border-radius:8px;padding:10px 12px;margin-top:8px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--accent);
                        letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">✓ Generation Complete</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:var(--muted);line-height:1.7;">
                {n_synth:,} rows generated<br>SCI Score: <span style="color:var(--accent);font-weight:700;">{sci_val}/100</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif gen_status == "error":
        st.error("Generation failed. Check your dataset and retry.")

    st.markdown("---")
    if st.button("↺ Reset Analysis", use_container_width=True):
        for k in ["synth_df","trust_metrics","gen_status","ai_explanation",
                  "ai_use_case_saved","uploaded_file_bytes","uploaded_file_name"]:
            st.session_state.pop(k, None)
        st.rerun()

    if st.button("Sign Out", use_container_width=True):
        sign_out()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="app-hero">
    <div class="app-hero-title">Data<span>Synth</span>X</div>
    <div class="app-hero-sub">🧬 Synthetic Data Generation Platform · Bayantx360 Suite</div>
</div>
""", unsafe_allow_html=True)

_has_file = (
    uploaded_file is not None or
    bool(st.session_state.get("uploaded_file_bytes"))
)

if not _has_file:
    st.markdown("""
    <div style="border:2px dashed var(--border);border-radius:16px;padding:60px;text-align:center;margin-top:20px;">
        <div style="font-size:3rem;margin-bottom:16px;">🧬</div>
        <div style="font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:700;color:var(--text);margin-bottom:8px;">No Dataset Loaded</div>
        <div style="font-family:'DM Mono',monospace;font-size:0.72rem;color:var(--muted);line-height:1.9;">
            Upload a CSV or Excel file in the sidebar to begin.<br>
            DataSynthX will profile your data and generate statistically faithful synthetic records.
        </div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, step, title, desc, color in [
        (c1, "01", "Upload & Profile", "Auto-detects numeric, categorical & datetime columns. Computes distributions, correlations and missing value ratios.", "var(--accent2)"),
        (c2, "02", "Generate at Scale", "Multivariate Gaussian synthesis preserves correlations. Frequency-weighted categorical sampling. Up to 1M rows.", "var(--accent)"),
        (c3, "03", "Trust Metrics", "KS-test, Wasserstein distance, KL divergence and a composite Structural Consistency Index (SCI) 0–100.", "var(--accent3)"),
    ]:
        with col:
            st.markdown(f"""
            <div class="scard" style="text-align:center;padding:32px 20px;">
                <div style="font-family:'DM Mono',monospace;font-size:0.58rem;color:var(--muted);letter-spacing:0.16em;text-transform:uppercase;margin-bottom:10px;">Step {step}</div>
                <div style="font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:{color};margin-bottom:8px;">{title}</div>
                <div style="font-size:0.72rem;color:var(--muted);line-height:1.8;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    st.stop()

# Load data
try:
    if uploaded_file is not None:
        fb = uploaded_file.read()
        if fb:
            st.session_state.uploaded_file_bytes = fb
            st.session_state.uploaded_file_name  = uploaded_file.name
    _file_bytes = st.session_state.get("uploaded_file_bytes")
    _file_name  = st.session_state.get("uploaded_file_name", "upload")
    if not _file_bytes:
        st.error("Could not read the uploaded file. Please try uploading again.")
        st.stop()
    df = load_data(_file_bytes, _file_name)
except Exception as e:
    st.error(f"Failed to load file: {e}")
    st.stop()

profiler = DataProfiler(df)
profile  = profiler.profile()
numeric_cols     = profile["numeric_cols"]
categorical_cols = profile["categorical_cols"]

# Quick stats
c1, c2, c3, c4, c5 = st.columns(5)
for col, val, label, color in [
    (c1, str(df.shape[0]),                     "Original Rows",    "var(--accent2)"),
    (c2, str(df.shape[1]),                     "Total Columns",    "var(--accent)"),
    (c3, str(len(numeric_cols)),               "Numeric Cols",     "var(--accent2)"),
    (c4, str(len(categorical_cols)),           "Categorical Cols", "var(--accent)"),
    (c5, f"{df.isna().mean().mean()*100:.1f}%","Missing Rate",     "var(--accent3)"),
]:
    with col:
        st.markdown(f"""
        <div class="scard" style="text-align:center;padding:18px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.12em;color:var(--muted);margin-bottom:6px;">{label}</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:{color};line-height:1;">{val}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Profile", "🧬 Synthetic Data", "📐 Trust Metrics", "⬇ Export"])

# ─────────────────── TAB 1: DATA PROFILE ──────────────────────────────────────
with tab1:
    st.markdown('<div class="scard-title">Original Dataset Preview</div>', unsafe_allow_html=True)
    st.dataframe(df.head(100), use_container_width=True, height=240)

    if numeric_cols:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Numeric Column Statistics</div>', unsafe_allow_html=True)
        stats_rows = []
        for col in numeric_cols:
            s = profile["numeric_stats"][col]
            stats_rows.append({
                "Column": col, "Mean": f"{s['mean']:.4f}", "Std Dev": f"{s['std']:.4f}",
                "Min": f"{s['min']:.4f}", "Max": f"{s['max']:.4f}",
                "Skewness": f"{s['skew']:.4f}", "Kurtosis": f"{s['kurtosis']:.4f}",
                "Missing %": f"{s['missing_ratio']*100:.1f}%",
            })
        st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)

    if categorical_cols:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Categorical Column Summary</div>', unsafe_allow_html=True)
        cat_rows = []
        for col in categorical_cols:
            s = profile["categorical_stats"][col]
            top = sorted(s["frequencies"].items(), key=lambda x: -x[1])[:3]
            cat_rows.append({
                "Column": col, "Unique Values": s["n_unique"], "Mode": s["mode"],
                "Top 3": ", ".join([f"{k} ({v*100:.1f}%)" for k, v in top]),
                "Missing %": f"{s['missing_ratio']*100:.1f}%",
            })
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

    if not profile["correlation_matrix"].empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Correlation Matrix</div>', unsafe_allow_html=True)
        render_heatmap(profile["correlation_matrix"], "ORIGINAL DATA — PEARSON CORRELATION")

    if numeric_cols:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Distribution Histograms</div>', unsafe_allow_html=True)
        for i in range(0, len(numeric_cols), 3):
            row_cols = st.columns(3)
            for j, col in enumerate(numeric_cols[i:i+3]):
                with row_cols[j]:
                    vals = df[col].dropna()
                    fig = go.Figure(go.Histogram(
                        x=vals, nbinsx=30,
                        marker=dict(color="#7c6df0", opacity=0.85, line=dict(width=0)),
                    ))
                    fig.update_layout(
                        title=dict(text=col, font=dict(size=10, color="#6b7a9a",
                                   family="DM Mono, monospace"), x=0),
                        paper_bgcolor="#111318", plot_bgcolor="#111318",
                        margin=dict(l=4, r=4, t=28, b=4), height=150,
                        xaxis=dict(showgrid=False, zeroline=False,
                                   tickfont=dict(size=8, color="#6b7a9a")),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        bargap=0.05,
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────── TAB 2: SYNTHETIC DATA ────────────────────────────────────
with tab2:
    if st.session_state.synth_df is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:2.5rem;margin-bottom:12px;">🧬</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:8px;">Ready to Generate</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);">Configure settings in the sidebar and click Generate Synthetic Data.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        synth_df = st.session_state.synth_df
        st.markdown('<div class="scard-title">Synthetic Dataset Preview</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.62rem;color:var(--muted);margin-bottom:10px;">{len(synth_df):,} rows generated · {synth_df.shape[1]} columns</div>', unsafe_allow_html=True)
        st.dataframe(synth_df.head(100), use_container_width=True, height=280)

        if numeric_cols:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Original vs Synthetic — Summary Comparison</div>', unsafe_allow_html=True)
            compare_rows = []
            for col in numeric_cols:
                o = df[col].dropna(); s = synth_df[col].dropna()
                compare_rows.append({
                    "Column": col,
                    "Orig Mean": f"{o.mean():.4f}", "Synth Mean": f"{s.mean():.4f}",
                    "Orig Std":  f"{o.std():.4f}",  "Synth Std":  f"{s.std():.4f}",
                    "Orig Min":  f"{o.min():.4f}",  "Synth Min":  f"{s.min():.4f}",
                    "Orig Max":  f"{o.max():.4f}",  "Synth Max":  f"{s.max():.4f}",
                })
            st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

        if numeric_cols:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Distribution Overlay — Original vs Synthetic</div>', unsafe_allow_html=True)
            for i in range(0, len(numeric_cols), 3):
                row_cols = st.columns(3)
                for j, col in enumerate(numeric_cols[i:i+3]):
                    with row_cols[j]:
                        fig = go.Figure()
                        fig.add_trace(go.Histogram(x=df[col].dropna(), name="Original", nbinsx=30,
                                                    marker=dict(color="#7c6df0", opacity=0.7, line=dict(width=0))))
                        fig.add_trace(go.Histogram(x=synth_df[col].dropna(), name="Synthetic", nbinsx=30,
                                                    marker=dict(color="#00e5c8", opacity=0.5, line=dict(width=0))))
                        fig.update_layout(
                            barmode="overlay",
                            title=dict(text=col, font=dict(size=10, color="#6b7a9a",
                                       family="DM Mono, monospace"), x=0),
                            paper_bgcolor="#111318", plot_bgcolor="#111318",
                            margin=dict(l=4, r=4, t=28, b=4), height=160,
                            xaxis=dict(showgrid=False, zeroline=False,
                                       tickfont=dict(size=8, color="#6b7a9a")),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            legend=dict(orientation="h", x=0, y=1.15,
                                       font=dict(size=9, color="#9aa3be"),
                                       bgcolor="rgba(0,0,0,0)"),
                            bargap=0.05,
                        )
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────── TAB 3: TRUST METRICS ─────────────────────────────────────
with tab3:
    if st.session_state.trust_metrics is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:2.5rem;margin-bottom:12px;">📐</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:8px;">Awaiting Generation</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);">Generate synthetic data first to see trust metrics.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        tm    = st.session_state.trust_metrics
        sci   = tm["sci"]
        color = score_color(sci)
        badge_cls, badge_label = score_badge(sci)

        pct           = sci / 100
        circumference = 2 * 3.14159 * 54
        dash          = circumference * pct
        gap           = circumference - dash

        st.markdown(f"""
        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:16px;
                    padding:32px;text-align:center;margin-bottom:24px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;
                        letter-spacing:0.18em;color:var(--muted);margin-bottom:16px;">
                Structural Consistency Index
            </div>
            <svg width="160" height="160" viewBox="0 0 120 120" style="display:block;margin:0 auto 12px;">
                <circle cx="60" cy="60" r="54" fill="none" stroke="var(--surface)" stroke-width="10"/>
                <circle cx="60" cy="60" r="54" fill="none" stroke="{color}" stroke-width="10"
                    stroke-dasharray="{dash:.1f} {gap:.1f}"
                    stroke-dashoffset="{circumference/4:.1f}"
                    stroke-linecap="round"/>
                <text x="60" y="56" text-anchor="middle" font-size="28" font-weight="800"
                      fill="{color}" font-family="Syne,sans-serif">{sci}</text>
                <text x="60" y="72" text-anchor="middle" font-size="10"
                      fill="#6b7a9a" font-family="DM Mono,monospace">/ 100</text>
            </svg>
            <span class="badge badge-teal" style="background:rgba(0,229,200,0.08);color:{color};
                  border-color:{color}33;">{badge_label}</span>
            <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);margin-top:12px;">
                Weighted composite of correlation, distribution and categorical fidelity scores
            </div>
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns(3)
        for col, label, score, note in [
            (sc1, "Correlation Preservation", tm["correlation_score"], "30% weight · Pearson matrix comparison"),
            (sc2, "Distribution Similarity",  tm["distribution_score"], "40% weight · KS-test · Wasserstein"),
            (sc3, "Categorical Fidelity",      tm["categorical_score"],  "30% weight · KL Divergence"),
        ]:
            with col:
                clr = score_color(score)
                st.markdown(f"""
                <div class="scard">
                    <div class="scard-title">{label}</div>
                    <div style="font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;
                                color:{clr};line-height:1;">{score}</div>
                    <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);
                                margin-top:6px;">{note}</div>
                </div>
                """, unsafe_allow_html=True)

        if not tm["orig_corr"].empty:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Correlation Matrix Comparison</div>', unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a: render_heatmap(tm["orig_corr"], "ORIGINAL DATA")
            with col_b: render_heatmap(tm["synth_corr"], "SYNTHETIC DATA")

        if tm["dist_scores"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Per-Column Distribution Metrics</div>', unsafe_allow_html=True)
            dist_rows = []
            for col_name, v in tm["dist_scores"].items():
                _, bt = score_badge(v["score"] * 100)
                dist_rows.append({
                    "Column": col_name, "KS Statistic": f"{v['ks_stat']:.4f}",
                    "KS p-value": f"{v['ks_pvalue']:.4f}",
                    "Wasserstein (norm.)": f"{v['wasserstein']:.4f}",
                    "Fidelity Score": f"{v['score']*100:.1f}", "Status": bt,
                })
            st.dataframe(pd.DataFrame(dist_rows), use_container_width=True, hide_index=True)

        if tm["cat_scores"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Categorical Distribution Fidelity</div>', unsafe_allow_html=True)
            cat_rows = []
            for col_name, v in tm["cat_scores"].items():
                _, bt = score_badge(v["score"] * 100)
                cat_rows.append({
                    "Column": col_name, "KL Divergence": f"{v['kl_divergence']:.4f}",
                    "Fidelity Score": f"{v['score']*100:.1f}", "Status": bt,
                })
            st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

        # AI Explainer
        st.markdown("---")
        st.markdown('<div class="scard-title">AI Quality Analysis</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);
                    line-height:1.8;margin-bottom:20px;">
            Tell the AI what you're building and it'll interpret your metrics — flagging what's working,
            what to watch, and whether your data is fit for purpose. Costs 1 credit.
        </div>
        """, unsafe_allow_html=True)

        if is_trial():
            render_locked_banner("AI Quality Analysis", is_trial_user=True)
            _, uc, _ = st.columns([1, 2, 1])
            with uc:
                st.link_button("⬡ Upgrade to Paid Plan →", "https://x.com/bayantx360", use_container_width=True)
        else:
            credits_left = st.session_state.user_credits
            use_case_input = st.text_area(
                "What are you using this synthetic data for?",
                placeholder="e.g. training a churn prediction model, anonymising patient records for research...",
                height=80, key="ai_use_case_input",
            )
            explain_disabled = credits_left <= 0
            if st.button("✦ Analyse Data Quality & Use-Case Fit", use_container_width=True, disabled=explain_disabled):
                if credits_left <= 0:
                    st.error("No credits remaining.")
                else:
                    dist_summary = {
                        col: {"ks_stat": round(v["ks_stat"], 4),
                              "wasserstein_norm": round(v["wasserstein"], 4),
                              "fidelity_score": round(v["score"] * 100, 1)}
                        for col, v in tm["dist_scores"].items()
                    } if tm["dist_scores"] else {}
                    cat_summary = {
                        col: {"kl_divergence": round(v["kl_divergence"], 4),
                              "fidelity_score": round(v["score"] * 100, 1)}
                        for col, v in tm["cat_scores"].items()
                    } if tm["cat_scores"] else {}
                    use_case = use_case_input.strip() or None
                    system_prompt = (
                        "You are a data scientist reviewing synthetic data quality results for a user. "
                        "Write 3–4 short paragraphs. No bullet points, no headers, no metric definitions. "
                        "Start by inferring what the dataset is likely for, then confirm/adjust based on stated use case. "
                        "Name specific columns when notably good or bad. Be direct about fitness for purpose. "
                        "End with one concrete actionable suggestion. Tone: like a colleague looking over your shoulder."
                    )
                    user_message = (
                        f"Dataset columns: {list(df.columns)}\n"
                        f"Original rows: {len(df)} → Synthetic rows: {len(st.session_state.synth_df)}\n"
                        f"SCI={tm['sci']}/100, Correlation={tm['correlation_score']}/100, "
                        f"Distribution={tm['distribution_score']}/100, Categorical={tm['categorical_score']}/100\n"
                        f"Per-column distribution: {dist_summary}\n"
                        f"Per-column categorical: {cat_summary}\n"
                        f"{'Use case: ' + use_case if use_case else 'No use case stated — infer from column names.'}"
                    )
                    with st.spinner("Analysing synthetic data quality…"):
                        try:
                            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                            resp = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "system", "content": system_prompt},
                                          {"role": "user",   "content": user_message}],
                                temperature=0.5, max_tokens=600,
                            )
                            explanation = resp.choices[0].message.content.strip()
                            handle_credit_deduction(1, app="DataSynthX", action="AI Trust Analysis")
                            st.session_state.ai_explanation   = explanation
                            st.session_state.ai_use_case_saved = use_case or "inferred from columns"
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI analysis failed: {e}")
            if explain_disabled:
                st.caption("⚠ No credits remaining.")
            else:
                st.caption(f"⚡ Costs 1 credit · {credits_left} remaining")

        if st.session_state.get("ai_explanation"):
            explanation  = st.session_state.ai_explanation
            stated_use   = st.session_state.get("ai_use_case_saved", "")
            html_text = (explanation
                         .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                         .replace("\n\n", "</p><p style='margin:0 0 14px 0;'>")
                         .replace("\n", " "))
            use_case_html = (
                f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:var(--muted);'
                f'background:rgba(0,229,200,0.05);border-radius:6px;padding:6px 10px;'
                f'margin-bottom:14px;border-left:2px solid var(--accent);">Use case: {stated_use}</div>'
                if stated_use and stated_use != "inferred from columns" else ""
            )
            st.markdown(
                '<div class="ai-label">✦ &nbsp; AI QUALITY ANALYSIS</div>'
                f'<div class="ai-box" style="white-space:normal;">'
                f'{use_case_html}'
                f'<p style="margin:0 0 14px 0;">{html_text}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ─────────────────── TAB 4: EXPORT ────────────────────────────────────────────
with tab4:
    if st.session_state.synth_df is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:2.5rem;margin-bottom:12px;">⬇</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;color:var(--text);">No Data to Export</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);margin-top:8px;">Generate synthetic data first.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        synth_df     = st.session_state.synth_df
        n_synth_rows = len(synth_df)
        sci_val      = st.session_state.get("trust_metrics", {}).get("sci", "N/A")
        clr          = score_color(float(sci_val)) if isinstance(sci_val, (int, float)) else "var(--accent)"
        credits_left = st.session_state.user_credits
        trial_active = is_trial()
        dl_cost      = download_credit_cost(n_synth_rows)

        st.markdown(f"""
        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:24px;
                    margin-bottom:24px;display:grid;grid-template-columns:repeat(4,1fr);gap:20px;">
            <div><div class="scard-title">Rows Generated</div>
                 <div style="font-size:1.5rem;font-weight:800;color:var(--accent2);">{n_synth_rows:,}</div></div>
            <div><div class="scard-title">Columns</div>
                 <div style="font-size:1.5rem;font-weight:800;color:var(--accent);">{synth_df.shape[1]}</div></div>
            <div><div class="scard-title">SCI Score</div>
                 <div style="font-size:1.5rem;font-weight:800;color:{clr};">{sci_val}</div></div>
            <div><div class="scard-title">Memory</div>
                 <div style="font-size:1.5rem;font-weight:800;color:var(--text);">{synth_df.memory_usage(deep=True).sum()//1024:,} KB</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Trial: export fully locked
        if trial_active:
            render_locked_banner("CSV & Excel Export", is_trial_user=True)
            _, uc, _ = st.columns([1, 2, 1])
            with uc:
                st.link_button("⬡ Upgrade to Paid Plan →", "https://x.com/bayantx360", use_container_width=True)
        else:
            # Credit cost info
            if dl_cost == 0:
                cost_label = "Download cost: Free (under 100 rows)"
                cost_color = "var(--accent)"
            else:
                tier = (
                    "100–500 rows → 1 credit" if n_synth_rows <= 500 else
                    "501–1,000 rows → 2 credits" if n_synth_rows <= 1000 else
                    "1,000+ rows → 5 credits"
                )
                cost_label = f"Download cost: {dl_cost} credit{'s' if dl_cost != 1 else ''} · {tier}"
                cost_color = "var(--warn)" if credits_left < dl_cost else "var(--accent2)"

            st.markdown(f"""
            <div style="background:rgba(0,229,200,0.04);border:1px solid rgba(0,229,200,0.15);
                        border-radius:10px;padding:12px 16px;margin-bottom:16px;
                        font-family:'DM Mono',monospace;font-size:0.7rem;color:{cost_color};">
                ⬡ {cost_label}
            </div>
            """, unsafe_allow_html=True)

            col_dl1, col_dl2 = st.columns(2)
            insufficient = dl_cost > 0 and credits_left < dl_cost

            for dl_col, fmt, label, fname, mime, data_fn in [
                (col_dl1, "CSV",   "⬇ Download CSV",
                 "datasynthx_synthetic.csv", "text/csv",
                 lambda: synth_df.to_csv(index=False).encode("utf-8")),
                (col_dl2, "Excel", "⬇ Download Excel (.xlsx)",
                 "datasynthx_synthetic.xlsx",
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 lambda: to_excel_bytes(synth_df)),
            ]:
                with dl_col:
                    st.markdown(f"""
                    <div class="scard" style="margin-bottom:12px;">
                        <div class="scard-title">{fmt} Export</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if insufficient:
                        st.markdown(f"""
                        <div class="locked-banner">
                            Insufficient credits. This download costs {dl_cost} credit{'s' if dl_cost != 1 else ''}
                            but you have {credits_left}. Please top up your plan.
                        </div>
                        """, unsafe_allow_html=True)
                        st.link_button("Get More Credits →", "https://x.com/bayantx360", use_container_width=True)
                    else:
                        try:
                            data = data_fn()
                            key  = f"dl_{fmt.lower()}_btn"
                            if st.download_button(label, data=data, file_name=fname, mime=mime,
                                                  key=key, use_container_width=True):
                                if dl_cost > 0:
                                    handle_credit_deduction(dl_cost, app="DataSynthX", action=f"Export ({fmt})")
                                    st.rerun()
                            if dl_cost == 0:
                                st.caption("No credit deducted · under 100 rows")
                            else:
                                st.caption(f"⚡ {dl_cost} credit{'s' if dl_cost != 1 else ''} deducted on download · {credits_left} remaining")
                        except Exception as e:
                            st.warning(f"{fmt} export unavailable: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATION TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════

if generate_btn:
    if not numeric_cols and not categorical_cols:
        st.session_state.gen_status = "error"
        st.error("No usable columns found. Please check your dataset.")
    else:
        with st.spinner(""):
            try:
                pb = st.progress(0, text="Initialising generator…")
                pb.progress(15, text="Building statistical model…")
                generator = SyntheticDataGenerator(df, profile)
                pb.progress(40, text=f"Generating {n_rows:,} synthetic rows…")
                synth_df = generator.generate(n_rows, noise_level=noise_level)
                pb.progress(70, text="Computing trust metrics…")
                tm = TrustMetrics(df, synth_df, profile)
                trust_data = tm.compute_sci()
                pb.progress(95, text="Finalising…")
                st.session_state.synth_df      = synth_df
                st.session_state.trust_metrics = trust_data
                st.session_state.gen_status    = "done"
                st.session_state.ai_explanation   = ""
                st.session_state.ai_use_case_saved = ""
                pb.progress(100, text="Done!")
            except Exception as err:
                st.session_state.gen_status = "error"
                st.error(f"Generation failed: {err}")
                st.rerun()

        sci   = trust_data["sci"]
        clr   = score_color(sci)
        badge_cls, badge_label = score_badge(sci)
        cred_display = "∞" if is_trial() else str(st.session_state.user_credits)
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(0,229,200,0.06),rgba(124,109,240,0.06));
                    border:1px solid rgba(0,229,200,0.25);border-radius:12px;
                    padding:20px 24px;margin-top:16px;display:flex;align-items:center;gap:16px;">
            <div style="font-size:2rem;">✓</div>
            <div>
                <div style="font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:var(--text);">
                    {n_rows:,} synthetic rows generated successfully
                </div>
                <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);margin-top:4px;">
                    SCI Score: <span style="color:{clr};font-weight:700;">{sci}/100</span> ·
                    Status: <span class="badge badge-teal" style="color:{clr};border-color:{clr}33;">{badge_label}</span> ·
                    Credits: <span style="color:var(--accent);font-weight:700;">{cred_display}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.rerun()

st.markdown("---")
st.markdown('<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.68rem;color:var(--muted);padding:10px 0;">🧬 DataSynthX · Synthetic Data Generation Platform · Bayantx360 Suite</div>', unsafe_allow_html=True)
