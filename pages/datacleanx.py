"""
apps/datacleanx.py
══════════════════════════════════════════════════════════════════════
Bayantx360 Suite — DataCleanX
Data Cleaning & Standardisation Platform
══════════════════════════════════════════════════════════════════════

Modules:
  • Module 1 — SmartProfiler      : auto-detects all data quality issues, emits Health Score
  • Module 2 — MissingValueHandler: per-column imputation strategies
  • Module 3 — OutlierManager     : visualise + cap/remove outliers per numeric column
  • Module 4 — ColumnStandardizer : type casting, case normalisation, whitespace, renaming
  • Module 5 — CleaningAuditLog   : human-readable log of every transformation applied

Credit model:
  • All analysis (profiling, Auto-Clean, manual cleaning) is FREE for trial and paid users.
  • Credits are only deducted on CSV / Excel export.
  • Export cost: free under 500 rows · 1 credit 500–1000 rows · 2 credits 1000+ rows.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import warnings
import sys, os
from datetime import datetime

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
    page_title="DataCleanX · Bayantx360 Suite",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
apply_suite_css()

if not st.session_state.get("access_granted"):
    st.switch_page(st.session_state["_home_page"])
    st.stop()

refresh_credits()

# Per-app session keys — reset on every fresh login.
# Using a login-generation counter ensures that if any key survived sign-out
# (e.g. was missed from SUITE_SESSION_KEYS), it still gets wiped on re-login.
_DCX_DEFAULTS = [
    ("clean_original_df",   None),
    ("clean_working_df",    None),
    ("clean_profile",       None),
    ("clean_audit_log",     []),
    ("clean_status",        None),
    ("uploaded_file_bytes", None),
    ("uploaded_file_name",  None),
    ("auto_clean_done",     False),
    ("outlier_decisions",   {}),
    ("col_rename_map",      {}),
    ("clean_has_changes",   False),
    ("clean_last_op_msg",   None),
    ("_uploaded_file_id",   None),
]

_current_user = st.session_state.get("user_key", "")
if st.session_state.get("_dcx_session_user") != _current_user:
    # New login (or first load) — forcibly reset all DataCleanX state
    for key, default in _DCX_DEFAULTS:
        st.session_state[key] = default
    st.session_state["_dcx_session_user"] = _current_user
else:
    # Same session — only set keys that are genuinely absent
    for key, default in _DCX_DEFAULTS:
        if key not in st.session_state:
            st.session_state[key] = default


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS  (FIX B5: moved above sidebar so clean_credit_cost is defined before use)
# ═══════════════════════════════════════════════════════════════════════════════

def health_color(score: float) -> str:
    if score >= 80: return "#00e5c8"
    if score >= 55: return "#7c6df0"
    return "#f05c7c"

def health_badge(score: float):
    if score >= 80: return "badge-teal",   "HEALTHY"
    if score >= 55: return "badge-purple", "NEEDS ATTENTION"
    return "badge-red", "CRITICAL"

def clean_credit_cost(n_rows: int, trial: bool = False) -> int:
    """
    Cleaning is always free. Export tiers:
      Trial users  : free for ≤50 rows · locked above 50 (upgrade required)
      Paid users   : 1 credit ≤1,000 rows · 2 credits >1,000 rows
    Returns 0 = free, -1 = locked (trial limit exceeded).
    """
    if trial:
        return 0 if n_rows <= 50 else -1
    if n_rows <= 1000: return 1
    return 2

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="CleanedData")
        wb = writer.book
        ws = writer.sheets["CleanedData"]
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#181c24",
                                  "font_color": "#00e5c8", "border": 1})
        for ci, col in enumerate(df.columns):
            ws.write(0, ci, col, hdr_fmt)
            ws.set_column(ci, ci, max(12, len(str(col)) + 4))
    return buf.getvalue()

def audit_log_to_text(logs: list) -> str:
    lines = [
        "DataCleanX — Cleaning Audit Log",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]
    for i, entry in enumerate(logs, 1):
        lines.append(f"{i:>3}. {entry}")
    lines.append("")
    lines.append(f"Total transformations applied: {len(logs)}")
    return "\n".join(lines)

def load_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Load CSV or Excel from bytes. No caching — must not persist across sessions."""
    name = file_name.lower()
    buf  = io.BytesIO(file_bytes)
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

def add_log(entry: str, feedback: str = None):
    """
    Append to the audit log, mark changes, and optionally queue a
    feedback toast that will be shown after the next st.rerun().
    Pass feedback=None to auto-derive it from the log entry.
    """
    if entry:
        st.session_state.clean_audit_log.append(entry)
        st.session_state.clean_has_changes = True
        msg = feedback if feedback is not None else entry
        st.session_state.clean_last_op_msg = ("success", msg)
    else:
        # Operation produced no log entry → nothing changed
        st.session_state.clean_last_op_msg = ("info", "No changes made — data already satisfies this condition.")

def show_op_feedback():
    """
    Render and clear the deferred operation feedback message.
    Call once near the top of Tab 2, after st.rerun() has fired.
    """
    msg_tuple = st.session_state.get("clean_last_op_msg")
    if msg_tuple:
        kind, text = msg_tuple
        st.session_state.clean_last_op_msg = None   # consume it
        if kind == "success":
            st.success(f"✓ {text}", icon="✅")
        elif kind == "info":
            st.info(text, icon="ℹ️")
        elif kind == "error":
            st.error(text)

def recompute_profile():
    if st.session_state.clean_working_df is not None:
        profiler = SmartProfiler(st.session_state.clean_working_df)
        st.session_state.clean_profile = profiler.profile()


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — SMART PROFILER
# ═══════════════════════════════════════════════════════════════════════════════

class SmartProfiler:
    """Read-only analysis. Does NOT modify the dataframe."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def _detect_missing(self) -> dict:
        result = {}
        for col in self.df.columns:
            n_missing = int(self.df[col].isna().sum())
            if n_missing > 0:
                result[col] = {"count": n_missing, "ratio": float(self.df[col].isna().mean())}
        return result

    def _detect_duplicates(self) -> int:
        return int(self.df.duplicated().sum())

    def _detect_outliers(self) -> dict:
        result = {}
        for col in self.df.select_dtypes(include=[np.number]).columns:
            s = self.df[col].dropna()
            if len(s) < 4:
                continue
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr    = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            mask   = (s < lo) | (s > hi)
            n_out  = int(mask.sum())
            if n_out > 0:
                result[col] = {
                    "count":       n_out,
                    "ratio":       float(n_out / len(s)),
                    "lower_fence": float(lo),
                    "upper_fence": float(hi),
                }
        return result

    def _detect_type_mismatches(self) -> dict:
        result = {}
        for col in self.df.select_dtypes(include=["object"]).columns:
            s = self.df[col].dropna().astype(str)
            numeric_ratio = pd.to_numeric(s, errors="coerce").notna().mean()
            if numeric_ratio > 0.80:
                result[col] = {"suggested_type": "numeric", "confidence": float(numeric_ratio)}
                continue
            try:
                dt_ratio = pd.to_datetime(s, errors="coerce").notna().mean()
                if dt_ratio > 0.70:
                    result[col] = {"suggested_type": "datetime", "confidence": float(dt_ratio)}
            except Exception:
                pass
        return result

    def _detect_inconsistent_categories(self) -> dict:
        result = {}
        for col in self.df.select_dtypes(include=["object"]).columns:
            s                 = self.df[col].dropna().astype(str)
            raw_unique        = s.nunique()
            normalised_unique = s.str.strip().str.lower().nunique()
            if normalised_unique < raw_unique:
                result[col] = {
                    "raw_unique":        int(raw_unique),
                    "normalised_unique": int(normalised_unique),
                    "saveable":          int(raw_unique - normalised_unique),
                }
        return result

    def _detect_whitespace(self) -> list:
        result = []
        for col in self.df.select_dtypes(include=["object"]).columns:
            s = self.df[col].dropna().astype(str)
            if (s != s.str.lstrip()).any() or (s != s.str.rstrip()).any():
                result.append(col)
        return result

    def _compute_health_score(self, missing, duplicates, outliers,
                               type_issues, cat_issues, whitespace_cols) -> float:
        n_rows, n_cols = self.df.shape
        score = 100.0
        if missing:
            score -= min(30, (np.mean([v["ratio"] for v in missing.values()]) * 20) +
                             (len(missing) / n_cols * 10))
        if duplicates > 0:
            score -= min(20, (duplicates / n_rows) * 100)
        if outliers:
            score -= min(15, np.mean([v["ratio"] for v in outliers.values()]) * 50)
        score -= min(15, len(type_issues) * 5)
        score -= min(10, len(cat_issues) * 3)
        score -= min(10, len(whitespace_cols) * 2)
        return round(max(0.0, score), 1)

    def profile(self) -> dict:
        missing     = self._detect_missing()
        duplicates  = self._detect_duplicates()
        outliers    = self._detect_outliers()
        type_issues = self._detect_type_mismatches()
        cat_issues  = self._detect_inconsistent_categories()
        ws_cols     = self._detect_whitespace()
        return {
            "shape":            self.df.shape,
            "numeric_cols":     self.df.select_dtypes(include=[np.number]).columns.tolist(),
            "categorical_cols": self.df.select_dtypes(include=["object"]).columns.tolist(),
            "missing":          missing,
            "duplicates":       duplicates,
            "outliers":         outliers,
            "type_issues":      type_issues,
            "cat_issues":       cat_issues,
            "whitespace_cols":  ws_cols,
            "health_score":     self._compute_health_score(
                missing, duplicates, outliers, type_issues, cat_issues, ws_cols),
            "total_issues": (
                len(missing) + (1 if duplicates > 0 else 0) +
                len(outliers) + len(type_issues) + len(cat_issues) + len(ws_cols)
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — MISSING VALUE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class MissingValueHandler:
    STRATEGIES = [
        "Drop rows", "Fill with mean", "Fill with median",
        "Fill with mode", "Forward fill", "Backward fill", "Fill with constant",
    ]

    @staticmethod
    def auto_strategy(df: pd.DataFrame, col: str) -> str:
        if df[col].isna().mean() > 0.5:
            return "Drop rows"
        # FIX B1: only suggest mean/median when column is genuinely numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            try:
                skew = abs(df[col].skew())
                return "Fill with median" if skew > 1 else "Fill with mean"
            except Exception:
                pass
        return "Fill with mode"

    @staticmethod
    def apply(df: pd.DataFrame, col: str, strategy: str,
              constant_value: str = "") -> tuple:
        df       = df.copy()
        n_before = int(df[col].isna().sum())
        if n_before == 0:
            return df, ""

        # FIX B1: if mean/median requested on a non-numeric column, attempt coerce or fall back
        if strategy in ("Fill with mean", "Fill with median"):
            if not pd.api.types.is_numeric_dtype(df[col]):
                coerced = pd.to_numeric(df[col], errors="coerce")
                if coerced.notna().sum() > 0:
                    df[col] = coerced   # successfully coerced — proceed with numeric strategy
                else:
                    strategy = "Fill with mode"   # graceful fallback

        if strategy == "Drop rows":
            df  = df.dropna(subset=[col]).reset_index(drop=True)
            log = f"Column `{col}`: dropped {n_before} rows with missing values."

        elif strategy == "Fill with mean":
            val = df[col].mean()
            df[col] = df[col].fillna(val)
            log = f"Column `{col}`: {n_before} missing values filled with mean ({val:.4f})."

        elif strategy == "Fill with median":
            val = df[col].median()
            df[col] = df[col].fillna(val)
            log = f"Column `{col}`: {n_before} missing values filled with median ({val:.4f})."

        elif strategy == "Fill with mode":
            val = df[col].mode()
            if len(val) > 0:
                df[col] = df[col].fillna(val.iloc[0])
                log = f"Column `{col}`: {n_before} missing values filled with mode ('{val.iloc[0]}')."
            else:
                log = f"Column `{col}`: mode could not be determined; no changes made."

        elif strategy == "Forward fill":
            df[col] = df[col].ffill()
            log = f"Column `{col}`: {n_before} missing values filled using forward fill."

        elif strategy == "Backward fill":
            df[col] = df[col].bfill()
            log = f"Column `{col}`: {n_before} missing values filled using backward fill."

        elif strategy == "Fill with constant":
            df[col] = df[col].fillna(constant_value)
            log = f"Column `{col}`: {n_before} missing values filled with constant ('{constant_value}')."

        else:
            log = ""

        return df, log


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — OUTLIER MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class OutlierManager:
    @staticmethod
    def get_fences(series: pd.Series, iqr_multiplier: float = 1.5):
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        return q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr

    @staticmethod
    def apply(df: pd.DataFrame, col: str, decision: str,
              iqr_multiplier: float = 1.5) -> tuple:
        df     = df.copy()
        s      = df[col].dropna()
        lo, hi = OutlierManager.get_fences(s, iqr_multiplier)
        mask   = (df[col] < lo) | (df[col] > hi)
        n_out  = int(mask.sum())

        if n_out == 0 or decision == "Keep":
            return df, ""

        if decision == "Remove rows":
            df  = df[~mask].reset_index(drop=True)
            log = f"Column `{col}`: removed {n_out} outlier rows (IQR × {iqr_multiplier})."
        elif decision == "Cap (Winsorise)":
            df.loc[df[col] < lo, col] = lo
            df.loc[df[col] > hi, col] = hi
            log = (f"Column `{col}`: capped {n_out} outliers to "
                   f"[{lo:.4f}, {hi:.4f}] (IQR × {iqr_multiplier}).")
        else:
            log = ""

        return df, log

    @staticmethod
    def boxplot(df: pd.DataFrame, col: str) -> go.Figure:
        fig = go.Figure()
        fig.add_trace(go.Box(
            y=df[col].dropna(), name=col,
            marker_color="#7c6df0", line_color="#7c6df0",
            fillcolor="rgba(124,109,240,0.15)",
            boxpoints="outliers",
            marker=dict(color="#f05c7c", size=5, opacity=0.8),
        ))
        fig.update_layout(
            paper_bgcolor="#111318", plot_bgcolor="#111318",
            margin=dict(l=10, r=10, t=20, b=10), height=220,
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                       zeroline=False, tickfont=dict(size=9, color="#6b7a9a")),
            xaxis=dict(showticklabels=False),
            font=dict(color="#e2e8f4"),
            showlegend=False,
        )
        return fig


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — COLUMN STANDARDIZER
# ═══════════════════════════════════════════════════════════════════════════════

class ColumnStandardizer:
    @staticmethod
    def strip_whitespace(df: pd.DataFrame, col: str) -> tuple:
        df      = df.copy()
        before  = df[col].astype(str).copy()
        df[col] = df[col].astype(str).str.strip()
        changed = (before != df[col]).sum()
        log = f"Column `{col}`: stripped whitespace from {changed} values." if changed > 0 else ""
        return df, log

    @staticmethod
    def normalise_case(df: pd.DataFrame, col: str, mode: str = "Title Case") -> tuple:
        df = df.copy()
        if   mode == "Lowercase": df[col] = df[col].astype(str).str.lower()
        elif mode == "Uppercase": df[col] = df[col].astype(str).str.upper()
        else:                     df[col] = df[col].astype(str).str.title()
        return df, f"Column `{col}`: values normalised to {mode}."

    @staticmethod
    def cast_type(df: pd.DataFrame, col: str, target_type: str) -> tuple:
        df = df.copy()
        try:
            if target_type == "Numeric":
                df[col] = pd.to_numeric(df[col], errors="coerce")
                log = f"Column `{col}`: cast to numeric."
            elif target_type == "Datetime":
                df[col] = pd.to_datetime(df[col], errors="coerce")
                log = f"Column `{col}`: cast to datetime."
            elif target_type == "String":
                df[col] = df[col].astype(str)
                log = f"Column `{col}`: cast to string."
            else:
                log = ""
        except Exception as e:
            log = f"Column `{col}`: type cast failed — {e}."
        return df, log

    @staticmethod
    def rename_column(df: pd.DataFrame, old_name: str, new_name: str) -> tuple:
        df = df.copy()
        if old_name == new_name or new_name.strip() == "":
            return df, ""
        df  = df.rename(columns={old_name: new_name})
        return df, f"Column `{old_name}` renamed to `{new_name}`."

    @staticmethod
    def drop_duplicates(df: pd.DataFrame) -> tuple:
        before  = len(df)
        df      = df.drop_duplicates().reset_index(drop=True)
        removed = before - len(df)
        log = f"Removed {removed} duplicate rows." if removed > 0 else ""
        return df, log


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-CLEAN ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_auto_clean(df: pd.DataFrame, profile: dict) -> tuple:
    """
    Conservative auto-clean. Safe order: duplicates → whitespace →
    categories → type fixes → missing → outliers.
    FIX B1: type fixes are applied BEFORE missing-value imputation so that
    columns like revenue (stored as string) are cast to numeric first,
    making mean/median imputation safe.
    """
    logs    = []
    working = df.copy()

    # 1. Duplicates
    working, log = ColumnStandardizer.drop_duplicates(working)
    if log: logs.append(log)

    # 2. Whitespace
    for col in profile["whitespace_cols"]:
        if col in working.columns:
            working, log = ColumnStandardizer.strip_whitespace(working, col)
            if log: logs.append(log)

    # 3. Inconsistent categories → Title Case
    for col in profile["cat_issues"]:
        if col in working.columns:
            working, log = ColumnStandardizer.normalise_case(working, col, "Title Case")
            if log: logs.append(log)

    # 4. Type mismatches (BEFORE missing value imputation — FIX B1)
    for col, info in profile["type_issues"].items():
        if col in working.columns:
            target = "Numeric" if info["suggested_type"] == "numeric" else "Datetime"
            working, log = ColumnStandardizer.cast_type(working, col, target)
            if log: logs.append(log)

    # 5. Missing values — auto strategy per column (now safe because types fixed above)
    for col in list(profile["missing"].keys()):
        if col in working.columns:
            strategy = MissingValueHandler.auto_strategy(working, col)
            working, log = MissingValueHandler.apply(working, col, strategy)
            if log: logs.append(log)

    # 6. Outliers — cap (non-destructive)
    for col in profile["outliers"]:
        if col in working.columns:
            working, log = OutlierManager.apply(working, col, "Cap (Winsorise)")
            if log: logs.append(log)

    return working, logs


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="padding:14px 0 20px 0;border-bottom:1px solid var(--border);margin-bottom:18px;">
        <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;
                    color:var(--text);letter-spacing:-0.02em;">
            🧹 Data<span style="color:var(--accent2);">Clean</span>X
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);
                    margin-top:4px;letter-spacing:0.08em;">
            DATA CLEANING PLATFORM · BAYANTX360 SUITE
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_credit_hud()

    if st.button("⬡ Back to Suite", use_container_width=True):
        st.switch_page(st.session_state["_home_page"])

    st.markdown("---")
    st.markdown(
        '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.12em;'
        'color:var(--muted);margin-bottom:10px;">Upload Dataset</div>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "CSV or Excel", type=["csv", "xlsx", "xls"],
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        # Only reset state when the file identity changes (new name or size).
        # Without this guard the uploader fires on every rerun, which re-reads
        # the file and wipes clean_working_df — making every operation appear
        # to have no effect because the session state gets reset right after
        # the button writes to it.
        _incoming_id = f"{uploaded_file.name}:{uploaded_file.size}"
        if st.session_state.get("_uploaded_file_id") != _incoming_id:
            file_bytes = uploaded_file.read()
            if file_bytes:
                st.session_state._uploaded_file_id  = _incoming_id
                st.session_state.uploaded_file_bytes = file_bytes
                st.session_state.uploaded_file_name  = uploaded_file.name
                # Reset all working state for the new file
                st.session_state.clean_original_df = None
                st.session_state.clean_working_df  = None
                st.session_state.clean_profile     = None
                st.session_state.clean_audit_log   = []
                st.session_state.auto_clean_done   = False
                st.session_state.outlier_decisions = {}
                st.session_state.clean_has_changes = False
                st.session_state.clean_last_op_msg = None

    st.markdown("---")

    # Cleaning mode toggle
    st.markdown(
        '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.12em;'
        'color:var(--muted);margin-bottom:10px;">Cleaning Mode</div>',
        unsafe_allow_html=True,
    )
    auto_clean_mode = st.toggle(
        "Auto-Clean (recommended)", value=True,
        help="Applies safe conservative defaults across all detected issues. "
             "Turn off for manual column-by-column control.",
    )

    if auto_clean_mode:
        st.markdown("""
        <div style="background:rgba(0,229,200,0.04);border:1px solid rgba(0,229,200,0.15);
                    border-radius:8px;padding:10px 12px;font-family:'DM Mono',monospace;
                    font-size:0.62rem;color:var(--muted);line-height:1.7;">
            ✓ Drop duplicates<br>✓ Strip whitespace<br>✓ Normalise categories<br>
            ✓ Fix type mismatches<br>✓ Impute missing values<br>✓ Cap outliers (IQR)
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # FIX B2: Auto-Clean is FREE for ALL users — no credit gate, no trial block
    st.markdown(
        '<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:var(--accent);'
        'margin-bottom:6px;">✓ Cleaning is always free · 1–2 credits on export</div>',
        unsafe_allow_html=True,
    )
    auto_clean_btn = (
        st.button("🧹 Run Auto-Clean", type="primary", use_container_width=True)
        if auto_clean_mode else False
    )

    if st.session_state.clean_audit_log:
        st.markdown("---")
        n_ops = len(st.session_state.clean_audit_log)
        st.markdown(f"""
        <div style="background:rgba(0,229,200,0.06);border:1px solid rgba(0,229,200,0.22);
                    border-radius:8px;padding:10px 12px;margin-bottom:8px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--accent);
                        letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">✓ Cleaning Applied</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.6rem;color:var(--muted);">
                {n_ops} transformation{"s" if n_ops != 1 else ""} logged
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("↺ Reset All", use_container_width=True):
        for k in [
            "clean_original_df", "clean_working_df", "clean_profile",
            "clean_audit_log", "clean_status", "uploaded_file_bytes",
            "uploaded_file_name", "auto_clean_done", "outlier_decisions",
            "col_rename_map", "clean_has_changes", "clean_last_op_msg",
            "_uploaded_file_id", "_dcx_session_user",
        ]:
            st.session_state.pop(k, None)
        st.rerun()

    if st.button("Sign Out", use_container_width=True):
        # Clear Streamlit's data cache so no file data leaks to the next session
        st.cache_data.clear()
        sign_out()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="app-hero">
    <div class="app-hero-title">Data<span>Clean</span>X</div>
    <div class="app-hero-sub">🧹 Data Cleaning & Standardisation Platform · Bayantx360 Suite</div>
</div>
""", unsafe_allow_html=True)

_has_file = (
    uploaded_file is not None or
    bool(st.session_state.get("uploaded_file_bytes"))
)

if not _has_file:
    st.markdown("""
    <div style="border:2px dashed var(--border);border-radius:16px;padding:60px;
                text-align:center;margin-top:20px;">
        <div style="font-size:3rem;margin-bottom:16px;">🧹</div>
        <div style="font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:700;
                    color:var(--text);margin-bottom:8px;">No Dataset Loaded</div>
        <div style="font-family:'DM Mono',monospace;font-size:0.72rem;color:var(--muted);line-height:1.9;">
            Upload a CSV or Excel file in the sidebar to begin.<br>
            DataCleanX will profile your data and guide you through cleaning it.
        </div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    for col, step, title, desc, color in [
        (c1, "01", "Health Profile",    "Auto-detects missing values, duplicates, outliers, type mismatches, and inconsistent categories. Emits a 0–100 Health Score.", "var(--accent2)"),
        (c2, "02", "Auto or Manual",    "One-click Auto-Clean for conservative safe defaults, or go column-by-column for full control.", "var(--accent)"),
        (c3, "03", "Compare & Inspect", "Side-by-side diff of original vs cleaned data with change statistics.", "var(--accent2)"),
        (c4, "04", "Export + Audit Log","Download cleaned CSV or Excel. 1 credit up to 1,000 rows · 2 credits above.", "var(--accent3)"),
    ]:
        with col:
            st.markdown(f"""
            <div class="scard" style="text-align:center;padding:32px 20px;">
                <div style="font-family:'DM Mono',monospace;font-size:0.58rem;color:var(--muted);
                            letter-spacing:0.16em;text-transform:uppercase;margin-bottom:10px;">Step {step}</div>
                <div style="font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;
                            color:{color};margin-bottom:8px;">{title}</div>
                <div style="font-size:0.72rem;color:var(--muted);line-height:1.8;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    st.stop()


# ── Load data ──────────────────────────────────────────────────────────────────
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
    raw_df = load_data(_file_bytes, _file_name)
except Exception as e:
    st.error(f"Failed to load file: {e}")
    st.stop()

# Initialise working df on first load only — do NOT reset on every rerun
if st.session_state.clean_original_df is None:
    st.session_state.clean_original_df = raw_df.copy()
    st.session_state.clean_working_df  = raw_df.copy()
    st.session_state.clean_has_changes = False   # FIX B3: fresh upload = no changes

if st.session_state.clean_profile is None:
    profiler = SmartProfiler(st.session_state.clean_working_df)
    st.session_state.clean_profile = profiler.profile()

df      = st.session_state.clean_original_df
working = st.session_state.clean_working_df
profile = st.session_state.clean_profile


# ── Auto-Clean trigger (FIX B2: free for all users, no credit gate) ───────────
if auto_clean_btn:
    with st.spinner("Running Auto-Clean…"):
        profiler_fresh = SmartProfiler(st.session_state.clean_working_df)
        profile_fresh  = profiler_fresh.profile()
        cleaned, logs  = run_auto_clean(st.session_state.clean_working_df, profile_fresh)
        st.session_state.clean_working_df  = cleaned
        st.session_state.clean_audit_log  += logs
        st.session_state.auto_clean_done   = True
        st.session_state.clean_has_changes = True   # FIX B3/B4: mark changes made
        recompute_profile()
    if logs:
        st.success(f"Auto-Clean complete — {len(logs)} transformation(s) applied.")
    else:
        st.info("Auto-Clean ran successfully — no issues found, your data is already clean!")
    st.rerun()


# ── Quick stats bar ────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
hs    = profile["health_score"]
hcol  = health_color(hs)
_, hl = health_badge(hs)
for col, val, label, color in [
    (c1, str(df.shape[0]),                            "Original Rows",  "var(--accent2)"),
    (c2, str(working.shape[0]),                       "Working Rows",   "var(--accent)"),
    (c3, str(working.shape[1]),                       "Columns",        "var(--accent2)"),
    (c4, f"{working.isna().mean().mean()*100:.1f}%",  "Missing Rate",   "var(--accent3)"),
    (c5, f"{hs}",                                     "Health Score",   hcol),
]:
    with col:
        st.markdown(f"""
        <div class="scard" style="text-align:center;padding:18px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;
                        letter-spacing:0.12em;color:var(--muted);margin-bottom:6px;">{label}</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;
                        color:{color};line-height:1;">{val}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📋 Data Health", "🧹 Clean", "🔍 Compare", "⬇ Export"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DATA HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    pct           = hs / 100
    circumference = 2 * 3.14159 * 54
    dash          = circumference * pct
    gap           = circumference - dash
    badge_cls, badge_label = health_badge(hs)

    st.markdown(f"""
    <div style="background:var(--surface2);border:1px solid var(--border);border-radius:16px;
                padding:32px;text-align:center;margin-bottom:24px;">
        <div style="font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;
                    letter-spacing:0.18em;color:var(--muted);margin-bottom:16px;">Data Health Score</div>
        <svg width="160" height="160" viewBox="0 0 120 120" style="display:block;margin:0 auto 12px;">
            <circle cx="60" cy="60" r="54" fill="none" stroke="var(--surface)" stroke-width="10"/>
            <circle cx="60" cy="60" r="54" fill="none" stroke="{hcol}" stroke-width="10"
                stroke-dasharray="{dash:.1f} {gap:.1f}"
                stroke-dashoffset="{circumference/4:.1f}" stroke-linecap="round"/>
            <text x="60" y="56" text-anchor="middle" font-size="28" font-weight="800"
                  fill="{hcol}" font-family="Syne,sans-serif">{hs}</text>
            <text x="60" y="72" text-anchor="middle" font-size="10"
                  fill="#6b7a9a" font-family="DM Mono,monospace">/ 100</text>
        </svg>
        <span class="badge badge-teal" style="background:rgba(0,229,200,0.08);color:{hcol};
              border-color:{hcol}33;">{badge_label}</span>
        <div style="font-family:'DM Mono',monospace;font-size:0.62rem;color:var(--muted);margin-top:12px;">
            {profile['total_issues']} issue type(s) detected across {df.shape[1]} columns
        </div>
    </div>
    """, unsafe_allow_html=True)

    issues_grid = [
        ("Missing Values",          len(profile["missing"]),         "columns affected",      "#f05c7c" if profile["missing"]         else "#00e5c8"),
        ("Duplicate Rows",          profile["duplicates"],           "duplicate rows",         "#f05c7c" if profile["duplicates"] > 0  else "#00e5c8"),
        ("Outlier Columns",         len(profile["outliers"]),        "columns with outliers",  "#7c6df0" if profile["outliers"]        else "#00e5c8"),
        ("Type Mismatches",         len(profile["type_issues"]),     "columns mistyped",       "#7c6df0" if profile["type_issues"]     else "#00e5c8"),
        ("Inconsistent Categories", len(profile["cat_issues"]),      "columns affected",       "#7c6df0" if profile["cat_issues"]      else "#00e5c8"),
        ("Whitespace Issues",       len(profile["whitespace_cols"]), "columns affected",       "#7c6df0" if profile["whitespace_cols"] else "#00e5c8"),
    ]
    row1 = st.columns(3)
    row2 = st.columns(3)
    for i, (label, val, sub, color) in enumerate(issues_grid):
        with (row1 if i < 3 else row2)[i % 3]:
            st.markdown(f"""
            <div class="scard" style="text-align:center;padding:20px;">
                <div class="scard-title">{label}</div>
                <div style="font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;
                            color:{color};line-height:1;">{val}</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.6rem;
                            color:var(--muted);margin-top:4px;">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

    if profile["missing"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Missing Values — Column Detail</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Column": col, "Missing Count": v["count"], "Missing %": f"{v['ratio']*100:.1f}%"}
            for col, v in profile["missing"].items()
        ]), use_container_width=True, hide_index=True)

    if profile["outliers"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Outlier Summary</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Column": col, "Outlier Count": v["count"],
             "Outlier %": f"{v['ratio']*100:.1f}%",
             "Lower Fence": f"{v['lower_fence']:.4f}",
             "Upper Fence": f"{v['upper_fence']:.4f}"}
            for col, v in profile["outliers"].items()
        ]), use_container_width=True, hide_index=True)

    if profile["type_issues"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="scard-title">Type Mismatch Detection</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Column": col, "Current Type": str(working[col].dtype),
             "Suggested Type": v["suggested_type"].capitalize(),
             "Confidence": f"{v['confidence']*100:.1f}%"}
            for col, v in profile["type_issues"].items()
        ]), use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="scard-title">Original Dataset Preview</div>', unsafe_allow_html=True)
    st.dataframe(df.head(100), use_container_width=True, height=240)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CLEAN
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    # Show deferred feedback from the previous operation (set before st.rerun())
    show_op_feedback()

    if auto_clean_mode:
        st.markdown("""
        <div style="background:rgba(0,229,200,0.04);border:1px solid rgba(0,229,200,0.2);
                    border-radius:12px;padding:16px 20px;margin-bottom:20px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:var(--accent);">
                ✓ Auto-Clean mode is ON — click <strong>Run Auto-Clean</strong> in the sidebar.
                Free for all users — no credits deducted.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(124,109,240,0.06);border:1px solid rgba(124,109,240,0.2);
                    border-radius:12px;padding:16px 20px;margin-bottom:20px;">
            <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:var(--accent2);">
                ⚙ Manual mode — apply transformations column by column below.
                All cleaning operations are free.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Duplicates ─────────────────────────────────────────────────────────────
    st.markdown('<div class="scard-title">Duplicate Rows</div>', unsafe_allow_html=True)
    dup_count = int(working.duplicated().sum())
    if dup_count == 0:
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:var(--accent);">✓ No duplicate rows detected.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#f05c7c;">{dup_count} duplicate rows found.</div>', unsafe_allow_html=True)
        if st.button("Remove Duplicates", key="rm_dup"):
            new_df, log = ColumnStandardizer.drop_duplicates(working)
            st.session_state.clean_working_df = new_df
            add_log(log, feedback=log if log else None)
            recompute_profile()
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Missing Values ─────────────────────────────────────────────────────────
    st.markdown('<div class="scard-title">Missing Value Imputation</div>', unsafe_allow_html=True)
    current_missing = {
        col: working[col].isna().sum()
        for col in working.columns if working[col].isna().sum() > 0
    }
    if not current_missing:
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:var(--accent);">✓ No missing values in working dataset.</div>', unsafe_allow_html=True)
    else:
        for col, n_miss in current_missing.items():
            with st.expander(f"`{col}` — {n_miss} missing ({n_miss/len(working)*100:.1f}%)"):
                # FIX B1: only offer mean/median for numeric columns in UI
                if pd.api.types.is_numeric_dtype(working[col]):
                    available_strategies = MissingValueHandler.STRATEGIES
                else:
                    available_strategies = [
                        s for s in MissingValueHandler.STRATEGIES
                        if s not in ("Fill with mean", "Fill with median")
                    ]
                auto_strat = MissingValueHandler.auto_strategy(working, col)
                if auto_strat not in available_strategies:
                    auto_strat = "Fill with mode"
                strategy = st.selectbox(
                    "Strategy", available_strategies,
                    index=available_strategies.index(auto_strat),
                    key=f"miss_strat_{col}",
                )
                const_val = ""
                if strategy == "Fill with constant":
                    const_val = st.text_input("Constant value", key=f"miss_const_{col}")
                if st.button("Apply", key=f"miss_apply_{col}"):
                    new_df, log = MissingValueHandler.apply(working, col, strategy, const_val)
                    st.session_state.clean_working_df = new_df
                    add_log(log)
                    recompute_profile()
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Outliers ───────────────────────────────────────────────────────────────
    st.markdown('<div class="scard-title">Outlier Management</div>', unsafe_allow_html=True)
    current_outliers = {}
    for col in working.select_dtypes(include=[np.number]).columns:
        s = working[col].dropna()
        if len(s) < 4:
            continue
        lo, hi = OutlierManager.get_fences(s)
        n_out  = int(((s < lo) | (s > hi)).sum())
        if n_out > 0:
            current_outliers[col] = n_out

    if not current_outliers:
        st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:var(--accent);">✓ No outliers detected in current working dataset.</div>', unsafe_allow_html=True)
    else:
        for col, n_out in current_outliers.items():
            with st.expander(f"`{col}` — {n_out} outlier(s)"):
                st.plotly_chart(
                    OutlierManager.boxplot(working, col),
                    use_container_width=True, config={"displayModeBar": False},
                )
                iqr_mult = st.slider("IQR multiplier", 1.0, 3.0, 1.5, 0.1, key=f"iqr_{col}")
                decision = st.radio(
                    "Action", ["Keep", "Cap (Winsorise)", "Remove rows"],
                    key=f"out_dec_{col}", horizontal=True,
                )
                if st.button("Apply", key=f"out_apply_{col}"):
                    new_df, log = OutlierManager.apply(working, col, decision, iqr_mult)
                    st.session_state.clean_working_df = new_df
                    add_log(log)
                    recompute_profile()
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Column Standardiser ────────────────────────────────────────────────────
    st.markdown('<div class="scard-title">Column Standardisation</div>', unsafe_allow_html=True)
    for col in working.columns:
        with st.expander(f"`{col}`  ·  {str(working[col].dtype)}"):
            sub1, sub2, sub3 = st.columns(3)

            with sub1:
                st.markdown("**Rename**")
                new_name = st.text_input("New name", value=col, key=f"rename_{col}")
                if st.button("Rename", key=f"rename_btn_{col}"):
                    new_df, log = ColumnStandardizer.rename_column(working, col, new_name)
                    st.session_state.clean_working_df = new_df
                    add_log(log)
                    recompute_profile()
                    st.rerun()

            with sub2:
                st.markdown("**Cast Type**")
                target_type = st.selectbox(
                    "Target type", ["(no change)", "Numeric", "Datetime", "String"],
                    key=f"cast_{col}",
                )
                if st.button("Cast", key=f"cast_btn_{col}") and target_type != "(no change)":
                    new_df, log = ColumnStandardizer.cast_type(working, col, target_type)
                    st.session_state.clean_working_df = new_df
                    add_log(log)
                    recompute_profile()
                    st.rerun()

            if pd.api.types.is_object_dtype(working[col]):
                with sub3:
                    st.markdown("**Text Ops**")
                    if st.button("Strip whitespace", key=f"ws_{col}"):
                        new_df, log = ColumnStandardizer.strip_whitespace(working, col)
                        st.session_state.clean_working_df = new_df
                        add_log(log)
                        recompute_profile()
                        st.rerun()
                    case_mode = st.selectbox(
                        "Normalise case",
                        ["(no change)", "Lowercase", "Uppercase", "Title Case"],
                        key=f"case_{col}",
                    )
                    if st.button("Apply case", key=f"case_btn_{col}") and case_mode != "(no change)":
                        new_df, log = ColumnStandardizer.normalise_case(working, col, case_mode)
                        st.session_state.clean_working_df = new_df
                        add_log(log)
                        recompute_profile()
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPARE
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    orig = st.session_state.clean_original_df
    work = st.session_state.clean_working_df

    # FIX B3: show empty state until actual changes have been applied
    if not st.session_state.get("clean_has_changes", False):
        st.markdown("""
        <div style="border:2px dashed var(--border);border-radius:16px;padding:48px;
                    text-align:center;margin-top:8px;">
            <div style="font-size:2.5rem;margin-bottom:14px;">🔍</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;
                        color:var(--text);margin-bottom:8px;">No Cleaning Applied Yet</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);
                        line-height:1.9;">
                Run Auto-Clean or apply manual fixes in the Clean tab.<br>
                This view will show a side-by-side diff once changes have been made.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        rows_removed = len(orig) - len(work)

        dc1, dc2, dc3, dc4 = st.columns(4)
        for col, val, label, color in [
            (dc1, f"{rows_removed:+}",                         "Rows Changed",           "#f05c7c" if rows_removed < 0 else "#00e5c8"),
            (dc2, f"{orig.isna().sum().sum()}",                "Original Missing Cells",  "var(--muted)"),
            (dc3, f"{work.isna().sum().sum()}",                "Working Missing Cells",   "#00e5c8"),
            (dc4, f"{len(st.session_state.clean_audit_log)}", "Transformations Applied", "var(--accent2)"),
        ]:
            with col:
                st.markdown(f"""
                <div class="scard" style="text-align:center;padding:18px;">
                    <div style="font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;
                                letter-spacing:0.12em;color:var(--muted);margin-bottom:6px;">{label}</div>
                    <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;
                                color:{color};line-height:1;">{val}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            st.markdown('<div class="scard-title">Original Dataset</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:var(--muted);margin-bottom:6px;">{orig.shape[0]:,} rows · {orig.shape[1]} columns</div>', unsafe_allow_html=True)
            st.dataframe(orig.head(100), use_container_width=True, height=300)
        with right:
            st.markdown('<div class="scard-title">Cleaned Dataset</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-family:\'DM Mono\',monospace;font-size:0.6rem;color:var(--muted);margin-bottom:6px;">{work.shape[0]:,} rows · {work.shape[1]} columns</div>', unsafe_allow_html=True)
            st.dataframe(work.head(100), use_container_width=True, height=300)

        shared_num = [c for c in orig.select_dtypes(include=[np.number]).columns if c in work.columns]
        if shared_num:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Numeric Column Comparison</div>', unsafe_allow_html=True)
            cmp_rows = []
            for col in shared_num:
                o = orig[col].dropna()
                w = work[col].dropna()
                try:
                    cmp_rows.append({
                        "Column":        col,
                        "Orig Mean":     f"{o.mean():.4f}",
                        "Clean Mean":    f"{w.mean():.4f}",
                        "Orig Std":      f"{o.std():.4f}",
                        "Clean Std":     f"{w.std():.4f}",
                        "Orig Missing":  int(orig[col].isna().sum()),
                        "Clean Missing": int(work[col].isna().sum()),
                    })
                except Exception:
                    pass
            if cmp_rows:
                st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)

        if st.session_state.clean_audit_log:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="scard-title">Cleaning Audit Log Preview</div>', unsafe_allow_html=True)
            for i, entry in enumerate(st.session_state.clean_audit_log, 1):
                st.markdown(f"""
                <div style="font-family:'DM Mono',monospace;font-size:0.68rem;color:var(--muted);
                            padding:6px 12px;border-left:2px solid var(--accent);margin-bottom:4px;">
                    <span style="color:var(--accent);font-weight:700;">{i:02}.</span> {entry}
                </div>
                """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
    work = st.session_state.clean_working_df

    # FIX B4: gate on clean_has_changes flag, not on audit log length
    if not st.session_state.get("clean_has_changes", False):
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:2.5rem;margin-bottom:12px;">⬇</div>
            <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;
                        color:var(--text);">Nothing to Export Yet</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);
                        margin-top:8px;">Apply at least one cleaning transformation first.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        n_rows_exp   = len(work)
        credits_left = st.session_state.user_credits
        trial_active = is_trial()
        dl_cost      = clean_credit_cost(n_rows_exp, trial=trial_active)

        st.markdown(f"""
        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;
                    padding:24px;margin-bottom:24px;display:grid;
                    grid-template-columns:repeat(4,1fr);gap:20px;">
            <div>
                <div class="scard-title">Cleaned Rows</div>
                <div style="font-size:1.5rem;font-weight:800;color:var(--accent2);">{n_rows_exp:,}</div>
            </div>
            <div>
                <div class="scard-title">Columns</div>
                <div style="font-size:1.5rem;font-weight:800;color:var(--accent);">{work.shape[1]}</div>
            </div>
            <div>
                <div class="scard-title">Transformations</div>
                <div style="font-size:1.5rem;font-weight:800;color:var(--accent2);">{len(st.session_state.clean_audit_log)}</div>
            </div>
            <div>
                <div class="scard-title">Health Score</div>
                <div style="font-size:1.5rem;font-weight:800;
                            color:{health_color(profile['health_score'])};">{profile['health_score']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Trial: locked above 50 rows ────────────────────────────────────────
        if trial_active and dl_cost == -1:
            render_locked_banner(
                f"Export — your cleaned dataset has {n_rows_exp:,} rows (trial limit: 50)",
                is_trial_user=True,
            )
            st.markdown("""
            <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--muted);
                        margin-top:10px;text-align:center;">
                Upgrade to a paid plan to export datasets larger than 50 rows.
            </div>
            """, unsafe_allow_html=True)
            _, uc, _ = st.columns([1, 2, 1])
            with uc:
                if st.button("⬡ Upgrade to Paid Plan →", key="upgrade_cta", use_container_width=True, type="primary"):
                    st.switch_page(st.session_state["_home_page"])

        # ── Trial: free export ≤50 rows ────────────────────────────────────────
        elif trial_active and dl_cost == 0:
            st.markdown(f"""
            <div style="background:rgba(0,229,200,0.04);border:1px solid rgba(0,229,200,0.15);
                        border-radius:10px;padding:12px 16px;margin-bottom:16px;
                        font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--accent);">
                ✓ Free trial export · {n_rows_exp} rows (within the 50-row trial limit) · no credits deducted
            </div>
            """, unsafe_allow_html=True)

            col_dl1, col_dl2, col_dl3 = st.columns(3)
            with col_dl1:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">CSV Export</div></div>', unsafe_allow_html=True)
                csv_data = work.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇ Download CSV", data=csv_data,
                    file_name="datacleanx_cleaned.csv", mime="text/csv",
                    key="dl_csv", use_container_width=True,
                )
            with col_dl2:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">Excel Export</div></div>', unsafe_allow_html=True)
                try:
                    xlsx_data = to_excel_bytes(work)
                    st.download_button(
                        "⬇ Download Excel (.xlsx)", data=xlsx_data,
                        file_name="datacleanx_cleaned.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_xlsx", use_container_width=True,
                    )
                except Exception as e:
                    st.warning(f"Excel export unavailable: {e}")
            with col_dl3:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">Audit Log (.txt)</div></div>', unsafe_allow_html=True)
                log_text = audit_log_to_text(st.session_state.clean_audit_log)
                st.download_button(
                    "⬇ Download Audit Log", data=log_text.encode("utf-8"),
                    file_name="datacleanx_audit_log.txt", mime="text/plain",
                    key="dl_log", use_container_width=True,
                )
                st.caption("Always free · no credits deducted")

        # ── Paid users ─────────────────────────────────────────────────────────
        else:
            if dl_cost == 1:
                cost_label = "Download cost: 1 credit · up to 1,000 rows"
                cost_color = "var(--accent2)"
            else:
                cost_label = f"Download cost: 2 credits · {n_rows_exp:,} rows"
                cost_color = "var(--warn)" if credits_left < dl_cost else "var(--accent2)"
            if credits_left < dl_cost:
                cost_color = "var(--warn)"

            st.markdown(f"""
            <div style="background:rgba(0,229,200,0.04);border:1px solid rgba(0,229,200,0.15);
                        border-radius:10px;padding:12px 16px;margin-bottom:16px;
                        font-family:'DM Mono',monospace;font-size:0.7rem;color:{cost_color};">
                ⬡ {cost_label}
            </div>
            """, unsafe_allow_html=True)

            col_dl1, col_dl2, col_dl3 = st.columns(3)
            insufficient = dl_cost > 0 and credits_left < dl_cost

            with col_dl1:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">CSV Export</div></div>', unsafe_allow_html=True)
                if insufficient:
                    st.markdown(f'<div class="locked-banner">Insufficient credits ({credits_left} of {dl_cost} required).</div>', unsafe_allow_html=True)
                else:
                    csv_data = work.to_csv(index=False).encode("utf-8")
                    if st.download_button(
                        "⬇ Download CSV", data=csv_data,
                        file_name="datacleanx_cleaned.csv", mime="text/csv",
                        key="dl_csv", use_container_width=True,
                    ):
                        if dl_cost > 0:
                            handle_credit_deduction(dl_cost, app="DataCleanX", action="Export (CSV)")
                            st.rerun()

            with col_dl2:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">Excel Export</div></div>', unsafe_allow_html=True)
                if insufficient:
                    st.markdown(f'<div class="locked-banner">Insufficient credits ({credits_left} of {dl_cost} required).</div>', unsafe_allow_html=True)
                else:
                    try:
                        xlsx_data = to_excel_bytes(work)
                        if st.download_button(
                            "⬇ Download Excel (.xlsx)", data=xlsx_data,
                            file_name="datacleanx_cleaned.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_xlsx", use_container_width=True,
                        ):
                            if dl_cost > 0:
                                handle_credit_deduction(dl_cost, app="DataCleanX", action="Export (Excel)")
                                st.rerun()
                    except Exception as e:
                        st.warning(f"Excel export unavailable: {e}")

            with col_dl3:
                st.markdown('<div class="scard" style="margin-bottom:12px;"><div class="scard-title">Audit Log (.txt)</div></div>', unsafe_allow_html=True)
                log_text = audit_log_to_text(st.session_state.clean_audit_log)
                st.download_button(
                    "⬇ Download Audit Log", data=log_text.encode("utf-8"),
                    file_name="datacleanx_audit_log.txt", mime="text/plain",
                    key="dl_log", use_container_width=True,
                )
                st.caption("Always free · no credits deducted")


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.68rem;'
    'color:var(--muted);padding:10px 0;">'
    '🧹 DataCleanX · Data Cleaning & Standardisation Platform · Bayantx360 Suite'
    '</div>',
    unsafe_allow_html=True,
          )
