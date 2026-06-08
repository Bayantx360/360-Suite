"""
shared/auth.py
══════════════════════════════════════════════════════════════════════
Bayantx360 Suite — Unified Authentication & Credit Engine
══════════════════════════════════════════════════════════════════════

Single source of truth for:
  • Google Sheets connection (one shared sheet for all apps)
  • Key lookup and validation
  • Credit deduction (by row_index — fast, one write per call)
  • Live balance refresh
  • Session-state initialisation helpers
  • Trial-gate helpers

Sheet schema (columns, 1-based):
  A  Key           │  e.g. BTX-XXXX-XXXX-XXXX
  B  Credits       │  integer ≥ 0
  C  DatePurchased │  ISO date string
  D  Email         │  owner email

All apps import:
    from shared.auth import (
        init_session_state,
        lookup_key,
        get_live_credits,
        deduct_credits,
        is_trial,
        can_use_premium,
        render_credit_hud,
        SUITE_SESSION_KEYS,
    )
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

# ── Constants ──────────────────────────────────────────────────────────────────
GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME       = "Sheet1"
LOG_TAB          = "ActivityLog"
COL_KEY          = "Key"
COL_CREDITS      = "Credits"
COL_DATE         = "DatePurchased"
COL_EMAIL        = "Email"
COL_STATUS       = "Status"
REQUIRED_HEADERS = [COL_KEY, COL_CREDITS, COL_DATE, COL_EMAIL]

# All session keys the suite uses — used for clean logout / reset
SUITE_SESSION_KEYS = [
    "access_granted",
    "access_error",
    "is_free_trial",
    "user_key",
    "user_credits",
    "user_email",
    "user_row",
    "_credit_msg",
    # per-app state cleared on sign-out
    "df", "results", "ai_explanation", "model_type",
    "authenticated", "key_owner", "key_plan",
    "efa_result", "cfa_result", "synth_df",
    # per-app state cleared on sign-out — DataCleanX
    "clean_original_df", "clean_working_df", "clean_profile",
    "clean_audit_log", "clean_status", "auto_clean_done",
    "outlier_decisions", "col_rename_map",
    "clean_has_changes", "clean_last_op_msg", "_uploaded_file_id",
    "_dcx_session_user",
]


# ── Google Sheets connection ───────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_gsheet_client():
    """
    Build and cache a gspread client using GCP service-account from secrets.
    Cached at resource level — one connection per Streamlit server process.
    """
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=GSHEET_SCOPES)
    return gspread.authorize(creds)


def _get_worksheet():
    """Return the single unified keys worksheet."""
    gc = _get_gsheet_client()
    sheet_id = st.secrets["BAYANTX_SHEET_ID"]
    sh = gc.open_by_key(sheet_id)
    return sh.worksheet(SHEET_NAME)


def _get_all_records():
    """Fetch all non-empty rows from the sheet."""
    ws = _get_worksheet()
    records = ws.get_all_records(
        expected_headers=REQUIRED_HEADERS,
        value_render_option="UNFORMATTED_VALUE",
    )
    # Filter out ghost rows (blank rows Google Sheets sometimes returns)
    return [r for r in records if any(str(v).strip() for v in r.values())], ws


# ── Core auth functions ────────────────────────────────────────────────────────

def lookup_key(access_key: str) -> dict | None:
    """
    Validate an access key against the unified sheet.

    Returns dict:
        row_index      — 1-based sheet row (for fast cell writes)
        key            — the key string
        credits        — integer credit balance
        date_purchased — string
        email          — owner email
    Returns None if key not found.
    Raises on sheet errors (caller should wrap with try/except if needed).
    """
    try:
        records, _ = _get_all_records()
        for i, row in enumerate(records, start=2):  # start=2: row 1 is header
            if str(row.get(COL_KEY, "")).strip() == access_key.strip():
                return {
                    "row_index":      i,
                    "key":            row[COL_KEY],
                    "credits":        int(row.get(COL_CREDITS, 0)),
                    "date_purchased": str(row.get(COL_DATE, "")),
                    "email":          str(row.get(COL_EMAIL, "")),
                    "status":         str(row.get(COL_STATUS, "ACTIVE")).strip().upper(),
                }
        return None
    except Exception as e:
        st.error(f"Auth error during key lookup: {e}")
        return None


def get_live_credits(row_index: int) -> int:
    """
    Fetch the current credit balance directly from the sheet by row index.
    Use this to refresh the balance on every authenticated page load.
    Much faster than get_all_records — reads a single cell.
    """
    try:
        ws = _get_worksheet()
        # Column B = Credits (column index 2, 1-based)
        val = ws.cell(row_index, 2).value
        return int(val) if val is not None else 0
    except Exception:
        # Silently fall back to session-cached value
        return st.session_state.get("user_credits", 0)


def deduct_credits(row_index: int, current_credits: int, amount: int = 1) -> int:
    """
    Deduct `amount` credits from the sheet row.
    Uses row_index (stored in session on login) — no full re-scan needed.

    Returns the new credit balance.
    Falls back to current_credits if write fails (silent — error logged in sidebar).
    """
    try:
        ws = _get_worksheet()
        new_credits = max(0, current_credits - amount)
        ws.update_cell(row_index, 2, new_credits)   # Column B = Credits
        return new_credits
    except Exception as e:
        st.error(f"Credit deduction error: {e}")
        return current_credits


# ── Session-state helpers ──────────────────────────────────────────────────────

def init_session_state():
    """
    Initialise all suite-level session keys with safe defaults.
    Call once at the top of every app file, before any auth check.
    Idempotent — only sets keys that don't yet exist.
    """
    defaults = {
        "access_granted": False,
        "access_error":   "",
        "is_free_trial":  False,
        "user_key":       "",
        "user_credits":   0,
        "user_email":     "",
        "user_row":       None,
        "_credit_msg":    None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def refresh_credits():
    """
    Refresh live credit balance from the sheet for paid users.
    No-op for free trial (credits are virtual — no sheet row).
    Call once per page load, after init_session_state().
    """
    if not st.session_state.get("is_free_trial", False):
        row = st.session_state.get("user_row")
        if row:
            st.session_state.user_credits = get_live_credits(row)


def sign_out():
    """Clear all suite session state and rerun to show landing."""
    for key in SUITE_SESSION_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


# ── Trial & premium gate helpers ───────────────────────────────────────────────

def is_trial() -> bool:
    """True if the current session is a free trial."""
    return st.session_state.get("is_free_trial", False)


def can_use_premium() -> bool:
    """
    True if the user can use premium features (AI explainer, exports).
    Premium = paid user with credits > 0.
    """
    if is_trial():
        return False
    return st.session_state.get("user_credits", 0) > 0


def activate_free_trial():
    """Set session state for a free trial user and rerun."""
    st.session_state.access_granted = True
    st.session_state.access_error   = ""
    st.session_state.is_free_trial  = True
    st.session_state.user_key       = "FREE-TRIAL"
    st.session_state.user_credits   = 0          # trial has no credit balance
    st.session_state.user_email     = "Free Trial"
    st.session_state.user_row       = None
    st.rerun()


def process_key_login(entered_key: str) -> None:
    """
    Validate an entered key and set session state accordingly.
    Sets access_error on failure; sets full session on success and reruns.
    """
    if not entered_key.strip():
        st.session_state.access_error = "Please enter your access key."
        st.rerun()
        return

    with st.spinner("Verifying key…"):
        record = lookup_key(entered_key.strip())

    if record is None:
        st.session_state.access_error = "Invalid access key. Please try again."
    elif record.get("status") == "REVOKED":
        st.session_state.access_error = (
            "This access key has been revoked. "
            "Please contact support if you believe this is an error."
        )
    elif record["credits"] <= 0:
        st.session_state.access_error = (
            "Your credits have been exhausted. "
            "Please purchase more credits to continue."
        )
    else:
        st.session_state.access_granted = True
        st.session_state.access_error   = ""
        st.session_state.is_free_trial  = False
        st.session_state.user_key       = record["key"]
        st.session_state.user_credits   = record["credits"]
        st.session_state.user_email     = record["email"]
        st.session_state.user_row       = record["row_index"]

    st.rerun()


# ── Credit HUD renderer ────────────────────────────────────────────────────────

def render_credit_hud():
    """
    Render the credit balance HUD in the sidebar.
    Call this once inside `with st.sidebar:` in each app.

    Shows:
      • Email / account identifier
      • Credit balance with colour-coded progress bar
      • Trial label if applicable
      • Deferred credit notification if set
      • Warning if no credits remain
    """
    credits_left  = st.session_state.get("user_credits", 0)
    trial         = is_trial()
    email_display = st.session_state.get("user_email") or "—"

    # Colour coding: teal = healthy, amber = low, red = empty
    if trial:
        credit_color = "#00e5c8"
        credit_label = "Free Trial"
        credit_display = "∞"
        bar_width = "100"
    elif credits_left > 5:
        credit_color   = "#00e5c8"
        credit_label   = "Credits remaining"
        credit_display = str(credits_left)
        bar_width      = str(min(100, credits_left * 5))
    elif credits_left > 1:
        credit_color   = "#f5a623"
        credit_label   = f"{credits_left} credits left"
        credit_display = str(credits_left)
        bar_width      = str(min(100, credits_left * 5))
    elif credits_left == 1:
        credit_color   = "#f05c7c"
        credit_label   = "1 credit left!"
        credit_display = "1"
        bar_width      = "5"
    else:
        credit_color   = "#f05c7c"
        credit_label   = "No credits"
        credit_display = "0"
        bar_width      = "0"

    st.sidebar.markdown(f"""
    <div style="background:var(--surface2,#181c24);border:1px solid var(--border,#1f2535);
                border-radius:10px;padding:16px 18px;margin-bottom:20px;
                font-family:'DM Mono',monospace;">
        <div style="font-size:0.58rem;text-transform:uppercase;letter-spacing:0.14em;
                    color:var(--muted,#6b7a9a);margin-bottom:6px;">Account</div>
        <div style="font-size:0.68rem;color:var(--muted,#6b7a9a);margin-bottom:12px;
                    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{email_display}</div>
        <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:10px;">
            <span style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;
                         color:{credit_color};line-height:1;">{credit_display}</span>
            <span style="font-size:0.58rem;color:var(--muted,#6b7a9a);text-transform:uppercase;
                         letter-spacing:0.12em;">{credit_label}</span>
        </div>
        <div style="background:var(--border,#1f2535);border-radius:3px;height:3px;">
            <div style="height:3px;border-radius:3px;background:{credit_color};
                        width:{bar_width}%;transition:width 0.5s ease;"></div>
        </div>
        {"<div style='margin-top:10px;font-size:0.6rem;color:var(--muted,#6b7a9a);'>Trial: analysis only · exports &amp; AI locked</div>" if trial else ""}
    </div>
    """, unsafe_allow_html=True)

    # Deferred credit notification (set by deduct flow, shown after rerun)
    cmsg = st.session_state.get("_credit_msg")
    if cmsg:
        level, text = cmsg
        if level == "warn":
            st.sidebar.warning(text)
        elif level == "info":
            st.sidebar.info(text)
        st.session_state._credit_msg = None

    # No-credits warning for paid users
    if not trial and credits_left <= 0:
        st.sidebar.warning("⚠ No credits remaining. Exports and AI Explainer require credits.")


def log_activity(app: str, action: str, credits_used: int = 1) -> None:
    """
    Append one usage event to the ActivityLog sheet tab.
    Call immediately after a successful credit deduction.
    Silent on failure — never blocks the user flow.

    Args:
        app          — "PanelStatX" | "DataSynthX" | "EFActor"
        action       — human-readable label, e.g. "AI Explainer", "DOCX Export"
        credits_used — number of credits deducted for this action
    """
    if is_trial():
        return  # trial users have no row and no credits to log

    try:
        gc       = _get_gsheet_client()
        sheet_id = st.secrets["BAYANTX_SHEET_ID"]
        sh       = gc.open_by_key(sheet_id)

        try:
            ws = sh.worksheet(LOG_TAB)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=LOG_TAB, rows=5000, cols=6)
            ws.append_row(
                ["Timestamp", "App", "Key", "Email", "Action", "Credits"],
                value_input_option="USER_ENTERED",
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row(
            [
                timestamp,
                app,
                st.session_state.get("user_key",   ""),
                st.session_state.get("user_email",  ""),
                action,
                credits_used,
            ],
            value_input_option="USER_ENTERED",
        )
    except Exception:
        pass  # logging must never crash the app


def handle_credit_deduction(amount: int = 1, app: str = "", action: str = "") -> int:
    """
    Deduct credits, update session + deferred notification, and log the event.
    Returns new credit balance.
    Safe to call from any app — handles trial guard internally.

    Args:
        amount  — credits to deduct (default 1)
        app     — app name for activity log, e.g. "PanelStatX"
        action  — action label for activity log, e.g. "AI Explainer"
    """
    if is_trial():
        return 0   # trial users are never deducted

    row          = st.session_state.get("user_row")
    current      = st.session_state.get("user_credits", 0)
    new_credits  = deduct_credits(row, current, amount)
    st.session_state.user_credits = new_credits

    if new_credits == 0:
        st.session_state._credit_msg = ("warn", "⚠ You just used your last credit. Top up to continue.")
    elif new_credits <= 3:
        st.session_state._credit_msg = ("warn", f"⚠ Only {new_credits} credit(s) remaining.")
    else:
        st.session_state._credit_msg = None

    # Log to ActivityLog sheet if caller supplied context
    if app and action:
        log_activity(app=app, action=action, credits_used=amount)

    return new_credits
