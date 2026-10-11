"""
SahiPay  -  the web page (version 4.2: new name and logo).

Run it with:   streamlit run app.py
"""
import base64
import functools
import html as htmllib
import io
import os
import re
import unicodedata
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

from demo_data import make_demo_entries
from i18n import LANGS, job_label, state_label, t
from logic import (MIN_GROUP_SIZE, OVERTIME_CHOICES, QUICK_AMOUNTS, QUICK_DAYS,
                   build_letter_text, calc_range, calculate, clean_for_pdf,
                   group_summary, money, money2, paid_total, rate_age_days)
from storage import add_entry, load_entries

APP_VERSION = "4.2 (SahiPay)"

BRAND = "#109C6B"      # SahiPay green (from the logo)
NAVY = "#14223F"       # SahiPay navy (from the logo)


@functools.lru_cache(maxsize=1)
def load_brand():
    """
    Find logo.png (in the assets folder, or next to app.py) and prepare two small copies:
    a data address for the page banner and a picture for the browser tab icon.
    If the logo or the image tool is missing, the app still works with a plain rupee coin.
    """
    for path in ("assets/logo.png", "logo.png"):
        if os.path.exists(path):
            try:
                from PIL import Image
                img = Image.open(path).convert("RGBA")
                banner = img.resize((132, 132), Image.LANCZOS)
                buf = io.BytesIO()
                banner.save(buf, format="PNG", optimize=True)
                data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
                icon = img.resize((64, 64), Image.LANCZOS)
                return data_uri, icon, path
            except Exception:
                return None, None, None
    return None, None, None


LOGO_URI, LOGO_ICON, LOGO_PATH = load_brand()
st.set_page_config(page_title="SahiPay", page_icon=LOGO_ICON if LOGO_ICON is not None else "₹", layout="centered")

# ---------------------------------------------------------------- language
lang_choice = st.selectbox("🌐 Language / மொழி / भाषा / ಭಾಷೆ / ഭാഷ / భాష", list(LANGS.keys()), key="lang_choice")
lang = LANGS[lang_choice]


def T(key, **kw):
    return t(lang, key, **kw)


def esc(x):
    return htmllib.escape(str(x), quote=True)


# ---------------------------------------------------------------- regional look
# state -> (main colour, second colour, border pattern)
THEMES = {
    "Tamil Nadu": ("#8B1E2D", "#F2A541", "temple"), "Kerala": ("#1F6F54", "#D4A537", "stripe"),
    "Karnataka": ("#B3202A", "#F5C518", "temple"), "Andhra Pradesh": ("#1B6E8A", "#F2A541", "temple"),
    "Telangana": ("#B83A6B", "#F2A541", "temple"), "Maharashtra": ("#C85A0B", "#2E7D5B", "zigzag"),
    "Gujarat": ("#B0175B", "#F2A541", "zigzag"), "Rajasthan": ("#C2452D", "#2A5C8C", "zigzag"),
    "Madhya Pradesh": ("#2A5C8C", "#F2A541", "zigzag"), "Uttar Pradesh": ("#C85A0B", "#1F6F54", "zigzag"),
    "Bihar": ("#8B5A00", "#8B1E2D", "zigzag"), "West Bengal": ("#B3202A", "#FFFFFF", "stripe"),
    "Odisha": ("#8B5A00", "#8B1E2D", "temple"), "Jharkhand": ("#2E7D5B", "#F2A541", "zigzag"),
    "Delhi": ("#1F3A6B", "#F2A541", "zigzag"), "Haryana": ("#2E7D5B", "#F2A541", "zigzag"),
    "Punjab": ("#C85A0B", "#1F3A6B", "zigzag"),
}


def darken(hex_colour, amount=0.28):
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c * (1 - amount)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def pattern_css(kind, primary, accent):
    """A repeating border like a saree edge: diamonds (temple), zigzag, or stripes."""
    if kind == "temple":
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='26' height='16'>"
               f"<path d='M13 1 L24 8 L13 15 L2 8 Z' fill='{primary}'/>"
               f"<circle cx='13' cy='8' r='3' fill='{accent}'/></svg>")
    elif kind == "zigzag":
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='22' height='16'>"
               f"<path d='M0 13 L5.5 3 L11 13 L16.5 3 L22 13' stroke='{primary}' stroke-width='3.2' fill='none'/>"
               f"<circle cx='11' cy='3' r='1.8' fill='{primary}'/></svg>")
    else:
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='16'>"
               f"<rect y='2' width='24' height='3' fill='{primary}'/><rect y='7' width='24' height='2' fill='{primary}'/>"
               f"<rect y='11' width='24' height='3' fill='{primary}'/></svg>")
    return 'url("data:image/svg+xml,' + quote(svg, safe="") + '")'


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Tamil:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&family=Noto+Sans+Kannada:wght@400;600;700&family=Noto+Sans+Malayalam:wght@400;600;700&family=Noto+Sans+Telugu:wght@400;600;700&display=swap');
.stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp input, .stApp textarea,
.hero, .rc, .note, .step, .upd, .mini, .join {font-family:'Noto Sans','Noto Sans Tamil','Noto Sans Devanagari','Noto Sans Kannada','Noto Sans Malayalam','Noto Sans Telugu',system-ui,sans-serif;}
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:760px; padding-top:1.1rem; padding-bottom:3rem;}

/* ---- top banner ---- */
.hero {position:relative; overflow:hidden; color:#fff; padding:18px 18px 16px;
       background:linear-gradient(135deg, PRIMARY 0%, PRIMARYDARK 100%); border-radius:18px 18px 0 0;}
.hero::after {content:""; position:absolute; right:-34px; top:-34px; width:150px; height:150px; border-radius:50%;
              background:rgba(255,255,255,.07); box-shadow:0 0 0 20px rgba(255,255,255,.05), 0 0 0 42px rgba(255,255,255,.03);}
.hero-in {display:flex; align-items:center; position:relative; z-index:1;}
.coin {flex:none; margin-right:14px; width:54px; height:54px; line-height:54px; text-align:center; border-radius:50%;
       background:ACCENT; color:PRIMARY; font-size:1.8rem; font-weight:700;
       box-shadow:0 0 0 4px rgba(255,255,255,.35), 0 4px 10px rgba(0,0,0,.25);}
.logo {flex:none; margin-right:14px; width:66px; height:66px; border-radius:50%; background:#fff;
        box-shadow:0 0 0 3px rgba(255,255,255,.55), 0 4px 12px rgba(0,0,0,.28);}
.hero-t {font-size:1.7rem; font-weight:800; letter-spacing:.02em; line-height:1.2;}
.hero-s {margin-top:2px; opacity:.95; font-size:1rem;}
.chips {display:flex; flex-wrap:wrap; margin-top:12px; position:relative; z-index:1;}
.chips span {margin:0 8px 6px 0; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.4); border-radius:999px;
             padding:3px 11px; font-size:.82rem;}
.border-strip {height:18px; margin-bottom:16px; border-radius:0 0 18px 18px; background-color:ACCENT;
               background-image:PATTERN; background-repeat:repeat-x; background-position:center;}

/* ---- tabs ---- */
button[data-baseweb="tab"] {font-size:.98rem; font-weight:600; padding:10px 10px;}
button[data-baseweb="tab"][aria-selected="true"] {color:PRIMARY;}
div[data-baseweb="tab-highlight"] {background-color:PRIMARY;}

/* ---- step headers ---- */
.step {display:flex; align-items:center; margin:4px 0 6px;}
.step-n {flex:none; margin-right:10px; width:32px; height:32px; border-radius:50%; background:PRIMARY; color:#fff; font-weight:700;
         display:flex; align-items:center; justify-content:center; box-shadow:0 2px 6px rgba(0,0,0,.2);}
.step-t {font-weight:700; font-size:1.12rem;}

/* ---- answer buttons look like pills ---- */
div[role="radiogroup"] {gap:8px; flex-wrap:wrap;}
div[role="radiogroup"] > label {border:1.5px solid rgba(120,120,120,.45); border-radius:999px; padding:7px 15px;
        background:#FFFFFF; color:#2B1B17; cursor:pointer; margin:0;}
div[role="radiogroup"] > label:hover {border-color:PRIMARY;}
div[role="radiogroup"] > label > div:first-child {display:none;}
div[role="radiogroup"] > label:has(input:checked) {background:PRIMARY; border-color:PRIMARY; box-shadow:0 2px 8px rgba(0,0,0,.2);}
div[role="radiogroup"] > label:has(input:checked) * {color:#FFFFFF !important;}
div[role="radiogroup"] > label p {font-size:1rem;}

/* ---- big buttons ---- */
.stButton > button, .stDownloadButton > button {width:100%; border-radius:12px; font-size:1.05rem; font-weight:600;
        padding:.7rem 1rem; border:2px solid PRIMARY; color:PRIMARY; background:#FFFFFF;}
.stButton > button:hover, .stDownloadButton > button:hover {background:PRIMARY; color:#FFFFFF; border-color:PRIMARY;}
.stButton > button:disabled {opacity:.55;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}

/* ---- result card ---- */
.rc {border-radius:18px; padding:16px 18px 14px; margin:8px 0 12px; box-shadow:0 4px 14px rgba(0,0,0,.12);}
.rc-under {background:#FFF1EC; color:#4A1D12; border-left:9px solid #C8553D;}
.rc-fine {background:#EAF6EF; color:#123B2B; border-left:9px solid #2E7D5B;}
.rc-unclear {background:#FFF6E3; color:#4A3300; border-left:9px solid #F2A541;}
.rc-top {font-size:.85rem; letter-spacing:.04em; text-transform:uppercase; opacity:.75; font-weight:600;}
.rc-amount {font-size:2.5rem; font-weight:800; line-height:1.15; margin:2px 0;}
.rc-msg {font-size:1.02rem; font-weight:600;}
.rc-bar {height:12px; background:rgba(0,0,0,.12); border-radius:999px; margin:12px 0 4px; overflow:hidden;}
.rc-bar div {height:100%; border-radius:999px; background:PRIMARY;}
.rc-pct {font-size:.88rem; opacity:.85;}
.rc-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:12px;}
.rc-grid div {background:rgba(255,255,255,.75); border-radius:12px; padding:8px 10px;}
.rc-grid small {display:block; font-size:.74rem; opacity:.75;}
.rc-grid b {font-size:1.02rem;}

/* ---- little totals cards ---- */
.mini-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:8px 0;}
.mini {background:#FFFFFF; color:#2B1B17; border-radius:14px; padding:10px 12px; border-top:5px solid PRIMARY;
       box-shadow:0 2px 8px rgba(0,0,0,.1);}
.mini small {display:block; font-size:.76rem; opacity:.75;}
.mini b {font-size:1.2rem;}
.mini-bad {border-top-color:#C8553D;}

/* ---- notes ---- */
.note {border-radius:12px; padding:10px 14px; margin:8px 0; font-size:.95rem; line-height:1.5;}
.note ul {margin:6px 0 2px 1.1rem; padding:0;}
.note-warn {background:#FFF6E3; color:#4A3300; border:1px solid #F2C97A;}
.note-info {background:#EAF1FA; color:#12304F; border:1px solid #B7CDE8;}
.note-ok {background:#EAF6EF; color:#123B2B; border:1px solid #A9D6BC;}

/* ---- updates + join button ---- */
.join {display:block; text-align:center; text-decoration:none !important; color:#FFFFFF !important; font-weight:700;
       background:#1FA855; padding:12px 16px; border-radius:14px; box-shadow:0 3px 10px rgba(0,0,0,.2); margin:6px 0 4px;}
.upd {background:#FFFFFF; color:#2B1B17; border-radius:14px; padding:12px 14px; margin:10px 0;
      border-left:7px solid ACCENT; box-shadow:0 2px 8px rgba(0,0,0,.1);}
.upd .badge {display:inline-block; font-size:.75rem; font-weight:700; border-radius:999px; padding:2px 10px;
             background:PRIMARY; color:#fff; margin-right:8px;}
.upd .badge-incident {background:#C8553D;}
.upd .when {font-size:.8rem; opacity:.7;}
.upd p {margin:6px 0 2px; font-size:1rem; line-height:1.55;}
.upd .src {font-size:.78rem; opacity:.65; word-break:break-all;}
.foot {text-align:center; font-size:.8rem; opacity:.7; margin-top:10px;}
</style>
"""

state_for_theme = st.session_state.get("sel_state", "Tamil Nadu")
STATE_PRIMARY, ACCENT, PATTERN = THEMES.get(state_for_theme, THEMES["Tamil Nadu"])
PRIMARY = BRAND
st.markdown(
    CSS.replace("PRIMARYDARK", darken(BRAND, 0.30)).replace("PRIMARY", BRAND)
       .replace("ACCENT", ACCENT).replace("PATTERN", pattern_css(PATTERN, STATE_PRIMARY, ACCENT)),
    unsafe_allow_html=True,
)
logo_html = (f'<img class="logo" src="{LOGO_URI}" alt="SahiPay logo">' if LOGO_URI
             else '<div class="coin">₹</div>')
st.markdown(
    f'<div class="hero"><div class="hero-in">{logo_html}'
    f'<div><div class="hero-t">{esc(T("title"))}</div><div class="hero-s">{esc(T("tagline"))}</div></div></div>'
    f'<div class="chips"><span>⏱ {esc(T("chip_fast"))}</span><span>🔒 {esc(T("chip_private"))}</span>'
    f'<span>✓ {esc(T("chip_free"))}</span></div></div><div class="border-strip"></div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- small building blocks
def card():
    """A bordered box (older Streamlit versions fall back to a plain box)."""
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()


def step_header(number, text):
    st.markdown(f'<div class="step"><div class="step-n">{number}</div><div class="step-t">{esc(text)}</div></div>',
                unsafe_allow_html=True)


def callout(kind, body_html):
    st.markdown(f'<div class="note note-{kind}">{body_html}</div>', unsafe_allow_html=True)


def mini_cards(items):
    """items = [(label, value, is_bad), ...]"""
    cells = "".join(
        f'<div class="mini{" mini-bad" if bad else ""}"><small>{esc(lab)}</small><b>{esc(val)}</b></div>'
        for lab, val, bad in items)
    st.markdown(f'<div class="mini-grid">{cells}</div>', unsafe_allow_html=True)


def clean_link(raw):
    """
    Clean a pasted link. Copying from WhatsApp, Numbers or Excel can add invisible
    characters (spaces, tabs, zero-width marks) that break the link without being
    visible. We remove them, and for WhatsApp links keep only the part that matters.
    """
    text = "".join(c for c in str(raw) if unicodedata.category(c) not in ("Cc", "Cf", "Zs", "Zl", "Zp"))
    m = re.search(r"https?://[^<>\"')]+", text)
    if not m:
        return ""
    url = m.group(0)
    w = re.match(r"(https://chat\.whatsapp\.com/[A-Za-z0-9_-]+)", url)
    return w.group(1) if w else url


def read_csv_safe(path):
    """
    Read a table file without ever crashing the app. It understands:
      - normal CSV files (several text formats, such as those saved by Excel or Numbers)
      - real Excel files (.xlsx), even if someone renamed them to .csv
    If the file is missing or unreadable, it returns None.
    """
    if not os.path.exists(path):
        return None
    raw = open(path, "rb").read()
    if raw[:4] == b"PK\x03\x04":                      # a real Excel file
        try:
            df = pd.read_excel(io.BytesIO(raw), dtype=str).fillna("")
        except Exception:
            return None
    else:
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            encodings = ["utf-16"]
        else:
            encodings = ["utf-8-sig", "cp1252", "latin-1"]
        text = None
        for enc in encodings:
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return None
        try:
            df = pd.read_csv(io.StringIO(text), keep_default_na=False)
        except Exception:
            return None
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


@st.cache_data
def load_data():
    df = read_csv_safe("min_wages.csv")
    df["rate_low"] = df["rate_low"].astype(float)
    df["rate_high"] = df["rate_high"].astype(float)
    return df


def make_pdf(text):
    """Turn the letter text into a PDF file (as bytes) that can be downloaded."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in clean_for_pdf(text).split("\n"):
        pdf.multi_cell(0, 7, line if line else " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def choice_or_type(label, values, key, fmt, type_label, min_value, max_value, default, step, index=0):
    """Show choices as pill buttons. The last choice lets the worker type a number instead."""
    opts = list(values) + ["__other__"]
    pick = st.radio(
        label, opts, index=index, key=key, horizontal=True,
        format_func=lambda v: T("other_type") if v == "__other__" else fmt(v),
    )
    if pick == "__other__":
        return st.number_input(type_label, min_value=min_value, max_value=max_value,
                               value=default, step=step, key=key + "_typed")
    return pick


def letter_block(prefix, state, job, days, ot_hours, rate_low, effective_from, source,
                 paid, result, rate_is_lowest, monthly=None):
    with card():
        st.markdown(f"#### 📄 {T('letter_title')}")
        st.caption(T("letter_caption"))
        worker_name = st.text_input(T("name_label"), key=prefix + "_name")
        employer_name = st.text_input(T("employer_label"), key=prefix + "_employer")
        place = st.text_input(T("place_label"), key=prefix + "_place")
        text = build_letter_text(
            worker_name, employer_name, place, state, job, days, ot_hours, rate_low,
            effective_from, source, paid, result, rate_is_lowest=rate_is_lowest, monthly=monthly,
        )
        st.download_button("⬇ " + T("download_btn"), data=make_pdf(text), file_name="complaint_letter.pdf",
                           mime="application/pdf", key=prefix + "_download")
        with st.expander(T("read_letter")):
            st.text(text)
        with st.expander(T("where_title")):
            st.markdown("\n".join("- " + T(f"where_{i}") for i in range(1, 5)))


def before_you_file():
    items = "".join(f"<li>{esc(T(f'bf_{i}'))}</li>" for i in range(1, 6))
    callout("warn", f"<b>⚠ {esc(T('bf_title'))}</b><ul>{items}</ul>")


data = load_data()

tab_check, tab_proof, tab_group, tab_rights, tab_about = st.tabs(
    [f"🧾 {T('tab_check')}", f"📅 {T('tab_proof')}", f"👥 {T('tab_group')}",
     f"📢 {T('tab_rights')}", f"ℹ️ {T('tab_about')}"]
)

# =====================================================================================
# TAB 1: check my pay
# =====================================================================================
with tab_check:
    # ---------- step 1: state + work
    with card():
        step_header(1, T("step1"))
        states = ["Tamil Nadu"] + sorted(s for s in data["state"].unique() if s != "Tamil Nadu")
        state = st.selectbox(T("q_state"), states, key="sel_state",
                             format_func=lambda s: state_label(lang, s))
        state_rows = data[data["state"] == state]

        jobs = list(dict.fromkeys(state_rows["industry"]))
        job = st.selectbox(T("q_work"), jobs, key=f"sel_job_{state}",
                           format_func=lambda j: job_label(lang, j))
        job_rows = state_rows[state_rows["industry"] == job]

        skills = list(dict.fromkeys(job_rows["skill_category"]))
        if len(skills) > 1:
            skill = st.radio(T("q_skill"), skills, key=f"sel_skill_{state}_{job}",
                             format_func=lambda k: T("skill_" + k))
        else:
            skill = skills[0]
        row = job_rows[job_rows["skill_category"] == skill].iloc[0]
        rate_low, rate_high = float(row["rate_low"]), float(row["rate_high"])
        exact = rate_low == rate_high
        conf = row["confidence"]

        if job == "Cracker / Fireworks Factory":
            callout("info", f"🧨 {esc(T('fw_note'))}")

    # ---------- step 2: days and hours
    with card():
        step_header(2, T("step2"))
        days = int(choice_or_type(T("q_days"), QUICK_DAYS, "pick_days", str, T("type_days"),
                                  1, 31, 26, 1, index=QUICK_DAYS.index(26)))
        ot_pick = st.radio(
            T("q_ot"), ["none", "low", "high", "other"], key="pick_ot", horizontal=True,
            format_func=lambda v: T("other_type") if v == "other" else T("ot_" + v),
        )
        if ot_pick == "other":
            ot_hours = float(st.number_input(T("type_ot"), min_value=0.0, max_value=400.0,
                                             value=0.0, step=1.0, key="pick_ot_typed"))
        else:
            ot_hours = OVERTIME_CHOICES[ot_pick] * days

    # ---------- step 3: pay
    with card():
        step_header(3, T("step3"))
        period = st.radio(T("q_period"), ["day", "week", "month"], key="pick_period", horizontal=True,
                          format_func=lambda v: T("period_" + v))
        amounts = QUICK_AMOUNTS[period]
        amount_each = float(choice_or_type(T("q_amount"), amounts, "pick_amount_" + period,
                                           lambda v: money(v), T("type_amount"),
                                           0.0, 1000000.0, 9000.0, 100.0, index=min(2, len(amounts) - 1)))
        paid = paid_total(period, amount_each, days)
        st.caption(f"{T('include_ot')}  {T('so_you_got', amount=money(paid), days=days)}")

    lo, hi, verdict = calc_range(rate_low, rate_high, days, ot_hours, paid)

    # ---------- the result card
    pct_got = 0 if lo["total_due"] <= 0 else max(0.0, min(100.0, paid / lo["total_due"] * 100))
    should_txt = money(lo["total_due"]) if exact else f"{money(lo['total_due'])} – {money(hi['total_due'])}"
    if verdict == "under":
        big = money(lo["shortfall"]) if exact else "≥ " + money(lo["shortfall"])
        msg = (T("msg_under", amount=money(lo["shortfall"])) if exact
               else T("msg_atleast", low=money(lo["shortfall"]), high=money(hi["shortfall"])))
        missing_txt = big
    elif verdict == "fine":
        big, msg, missing_txt = "✓", T("msg_fine"), money(0)
    else:
        big, msg, missing_txt = "?", T("msg_unclear"), "?"
    kind = {"under": "under", "fine": "fine", "unclear": "unclear"}[verdict]
    st.markdown(
        f'<div class="rc rc-{kind}" data-verdict="{kind}" data-should="{esc(should_txt)}" data-missing="{esc(missing_txt)}">'
        f'<div class="rc-top">{esc(T("result_title"))}</div>'
        f'<div class="rc-amount">{esc(big)}</div><div class="rc-msg">{esc(msg)}</div>'
        f'<div class="rc-bar"><div style="width:{pct_got:.0f}%"></div></div>'
        f'<div class="rc-pct">{esc(T("pct_got", pct=f"{pct_got:.0f}"))}</div>'
        f'<div class="rc-grid"><div><small>{esc(T("res_should"))}</small><b>{esc(should_txt)}</b></div>'
        f'<div><small>{esc(T("res_got"))}</small><b>{esc(money(paid))}</b></div>'
        f'<div><small>{esc(T("res_missing"))}</small><b>{esc(missing_txt)}</b></div></div></div>',
        unsafe_allow_html=True,
    )

    # ---------- notes about the numbers
    if exact:
        st.caption(T("rate_exact", rate=money2(rate_low)))
    else:
        st.caption(T("rate_range", low=money2(rate_low), high=money2(rate_high)))
    when = f" | {row['effective_from']}" if row["effective_from"] else ""
    st.caption(f"{T('source_label')}: {row['source']}{when}")

    age = rate_age_days(row["effective_from"])
    is_general = row.get("scope", "") == "general"
    if conf == "stand_in":
        callout("warn", f"⚠ {esc(T('warn_standin'))}")
    elif conf == "disputed":
        callout("warn", f"⚠ {esc(T('warn_disputed'))}")
        if is_general:
            callout("warn", f"⚠ {esc(T('warn_general'))}")
        else:
            callout("info", f"ℹ {esc(T('warn_zone'))}")
    elif conf == "indicative":
        callout("warn" if is_general else "info", f"{'⚠' if is_general else 'ℹ'} {esc(T('warn_general') if is_general else T('warn_zone'))}")
    elif conf == "older" or (age is not None and age > 183):
        callout("warn", f"⚠ {esc(T('warn_older'))}")

    with st.expander(T("how_calc")):
        st.write(T("calc_days", rate=money2(rate_low), days=days, amount=money(lo["basic_due"])))
        st.write(T("calc_ot", amount=money(lo["overtime_pay"])))
        st.write(T("calc_total", amount=money(lo["total_due"])))
        st.write(T("calc_missing", due=money(lo["total_due"]), paid=money(paid),
                   amount=money(max(lo["shortfall"], 0))))

    # ---------- what next
    if verdict == "under":
        st.markdown(f"### 👉 {T('next_steps')}")
        before_you_file()
        letter_block("single", state, job, days, ot_hours, rate_low, row["effective_from"],
                     row["source"], paid, lo, rate_is_lowest=not exact)

    # ---------- share without a name
    with card():
        st.markdown(f"#### 🤝 {T('share_title')}")
        st.caption(T("share_caption"))
        can_share = verdict in ("fine", "under") and conf != "stand_in"
        if can_share:
            already = st.session_state.get("shared", False)
            if st.button(T("share_btn"), disabled=already, key="share_button"):
                pct = (lo["shortfall"] / lo["total_due"] * 100) if verdict == "under" else 0.0
                add_entry(state, job, pct, max(lo["shortfall"], 0))
                st.session_state["shared"] = True
                callout("ok", f"✓ {esc(T('share_thanks'))}")
        else:
            st.caption(T("share_not_now"))

# =====================================================================================
# TAB 2: month by month proof (arrears)
# =====================================================================================
with tab_proof:
    st.markdown(f"### {T('proof_title')}")
    st.write(T("proof_intro"))
    st.caption(T("proof_for", job=job_label(lang, job), state=state_label(lang, state)))

    base = pd.DataFrame({"month": ["", "", ""], "days": [0, 0, 0],
                         "ot_hours": [0.0, 0.0, 0.0], "paid": [0.0, 0.0, 0.0]})
    edited = st.data_editor(
        base, num_rows="dynamic", hide_index=True, key="proof_editor",
        column_config={
            "month": st.column_config.TextColumn(T("col_month")),
            "days": st.column_config.NumberColumn(T("col_days"), min_value=0, max_value=31, step=1),
            "ot_hours": st.column_config.NumberColumn(T("col_ot"), min_value=0.0, step=0.5),
            "paid": st.column_config.NumberColumn(T("col_paid"), min_value=0.0, step=100.0),
        },
    )

    rec = edited.copy()
    rec["month"] = rec["month"].fillna("").astype(str)
    for col in ("days", "ot_hours", "paid"):
        rec[col] = pd.to_numeric(rec[col], errors="coerce").fillna(0)
    rec = rec[rec["days"] > 0]

    if rec.empty:
        callout("info", f"ℹ {esc(T('proof_empty'))}")
    else:
        monthly = []
        for _, r in rec.iterrows():
            res = calculate(rate_low, int(r["days"]), float(r["ot_hours"]), float(r["paid"]))
            monthly.append({"month": r["month"], "days": int(r["days"]), "ot_hours": float(r["ot_hours"]),
                            "paid": float(r["paid"]), "due": res["total_due"], "missing": res["shortfall"],
                            "basic": res["basic_due"], "ot_pay": res["overtime_pay"]})

        table = pd.DataFrame({
            T("col_month"): [m["month"] for m in monthly],
            T("col_days"): [m["days"] for m in monthly],
            T("col_ot"): [m["ot_hours"] for m in monthly],
            T("col_paid"): [round(m["paid"]) for m in monthly],
            T("col_due"): [round(m["due"]) for m in monthly],
            T("col_missing"): [round(max(m["missing"], 0)) for m in monthly],
        })
        st.dataframe(table, hide_index=True)

        total_due = sum(m["due"] for m in monthly)
        total_paid = sum(m["paid"] for m in monthly)
        arrears = sum(max(m["missing"], 0) for m in monthly)
        mini_cards([(T("total_due"), money(total_due), False), (T("total_paid"), money(total_paid), False),
                    (T("total_arrears"), money(arrears), arrears > 0)])
        st.caption(T("proof_caveat"))
        st.caption(T("proof_tip"))
        if not exact:
            callout("warn", f"⚠ {esc(T('warn_disputed'))}")
        if conf == "stand_in":
            callout("warn", f"⚠ {esc(T('warn_standin'))}")

        st.download_button("⬇ " + T("proof_csv"), data=table.to_csv(index=False).encode("utf-8-sig"),
                           file_name="month_by_month_record.csv", mime="text/csv", key="proof_csv")

        if arrears > 0:
            st.markdown(f"### 👉 {T('next_steps')}")
            before_you_file()
            total_result = {"total_due": total_due, "shortfall": arrears,
                            "basic_due": sum(m["basic"] for m in monthly),
                            "overtime_pay": sum(m["ot_pay"] for m in monthly)}
            letter_block("proof", state, job, sum(m["days"] for m in monthly),
                         sum(m["ot_hours"] for m in monthly), rate_low, row["effective_from"],
                         row["source"], total_paid, total_result, rate_is_lowest=not exact,
                         monthly=monthly)
        else:
            callout("ok", f"✓ {esc(T('proof_fine'))}")

# =====================================================================================
# TAB 3: group picture (+ lowest pay by job)
# =====================================================================================
def style_chart(fig, colour):
    fig.update_traces(marker_color=colour, textposition="outside", cliponaxis=False)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=0, r=30, t=10, b=10))
    return fig


with tab_group:
    st.markdown(f"### {T('group_title')}")
    st.write(T("group_intro"))
    use_demo = st.checkbox(T("demo_check"), value=True, key="use_demo")

    real = load_entries()
    parts = []
    if not real.empty:
        real = real[["state", "industry", "shortfall_percent"]].copy()
        real["source"] = "Shared by workers"
        parts.append(real)
    if use_demo:
        demo_jobs = data[(data["state"] == "Tamil Nadu") & (data["confidence"] != "stand_in")]["industry"].unique().tolist()
        parts.append(make_demo_entries(demo_jobs, state="Tamil Nadu"))

    if not parts:
        callout("info", f"ℹ {esc(T('group_empty'))}")
    else:
        summary, hidden = group_summary(pd.concat(parts, ignore_index=True))
        if summary.empty:
            callout("info", f"ℹ {esc(T('group_empty'))}")
        else:
            g_states = sorted(summary["state"].unique())
            g_state = st.selectbox(T("pick_state"), g_states, key="group_state",
                                   index=g_states.index("Tamil Nadu") if "Tamil Nadu" in g_states else 0,
                                   format_func=lambda s: state_label(lang, s))
            part = summary[summary["state"] == g_state].sort_values("avg_missing_percent").copy()
            part["label"] = part["industry"].map(lambda j: job_label(lang, j))
            fig = px.bar(part, x="avg_missing_percent", y="label", orientation="h",
                         text="avg_missing_percent", hover_data={"entries": True, "share_underpaid": True},
                         labels={"avg_missing_percent": T("group_avg"), "label": ""},
                         height=max(280, 34 * len(part)))
            st.plotly_chart(style_chart(fig, "#C8553D"))
            if use_demo:
                callout("warn", f"⚠ {esc(T('demo_warning'))}")
            st.caption(T("group_min", n=MIN_GROUP_SIZE))
            st.caption(T("group_rough"))

    st.divider()
    st.markdown(f"### {T('chart_min_title')}: {state_label(lang, state)}")
    shown = state_rows.copy()
    if (shown["scope"] == "industry").all():
        shown["label"] = shown["industry"].map(lambda j: job_label(lang, j))
        shown = shown.sort_values("rate_high")
        fig2 = px.bar(shown, x="rate_high", y="label", orientation="h", text="rate_high",
                      labels={"rate_high": T("chart_min_title"), "label": ""},
                      height=max(280, 26 * len(shown)))
        st.plotly_chart(style_chart(fig2, PRIMARY))
    else:
        shown = shown.drop_duplicates(subset=["skill_category"])
        st.dataframe(pd.DataFrame({
            T("col_work"): shown["skill_category"].map(lambda k: T("skill_" + k)),
            T("col_low"): shown["rate_low"].round(2),
            T("col_high"): shown["rate_high"].round(2),
        }), hide_index=True)
        callout("warn", f"⚠ {esc(T('warn_general'))}")
        if (state_rows["confidence"] == "disputed").any():
            callout("warn", f"⚠ {esc(T('warn_disputed'))}")
    st.caption(T("chart_min_note"))

# =====================================================================================
# TAB 4: rights & updates (+ WhatsApp)
# =====================================================================================
with tab_rights:
    st.markdown(f"### 💬 {T('channel_title')}")
    link, link_name = "", ""
    for channel_file in ("channels.csv", "channels.xlsx"):
        ch = read_csv_safe(channel_file)
        if ch is not None and {"language", "invite_link"} <= set(ch.columns):
            found = ch[ch["language"].astype(str).str.strip().str.lower() == lang]
            if not found.empty and clean_link(found.iloc[0]["invite_link"]):
                link = clean_link(found.iloc[0]["invite_link"])
                link_name = str(found.iloc[0].get("channel_name", "")).strip()
                break
    if link:
        label = f"{T('channel_join')}: {link_name}" if link_name else T("channel_join")
        st.markdown(f'<a class="join" href="{esc(link)}" target="_blank" rel="noopener noreferrer">💬 {esc(label)}</a>',
                    unsafe_allow_html=True)
        st.caption(link)
    else:
        callout("info", f"ℹ {esc(T('channel_soon'))}")

    st.markdown(f"### 📰 {T('updates_title')}")
    ups = read_csv_safe("updates.csv")
    if ups is not None and {"date", "language", "type", "text", "source"} <= set(ups.columns):
        ups = ups[(ups["language"] == lang) | (ups["type"] == "incident")].sort_values("date", ascending=False)
    else:
        ups = pd.DataFrame()
    if ups.empty:
        callout("info", f"ℹ {esc(T('no_updates'))}")
    else:
        for _, u in ups.iterrows():
            is_incident = u["type"] == "incident"
            badge = T("incident_label") if is_incident else T("tip_label")
            src = f'<div class="src">{esc(T("source_label"))}: {esc(u["source"])}</div>' if u["source"] else ""
            st.markdown(
                f'<div class="upd"><span class="badge{" badge-incident" if is_incident else ""}">{esc(badge)}</span>'
                f'<span class="when">{esc(u["date"])}</span><p>{esc(u["text"])}</p>{src}</div>',
                unsafe_allow_html=True)

# =====================================================================================
# TAB 5: about
# =====================================================================================
with tab_about:
    st.markdown(f"### {T('tab_about')}")
    if LOGO_PATH:
        st.image(LOGO_PATH, width=150)
    for i, icon in zip(range(1, 6), ["💡", "🧾", "🔒", "📊", "🌐"]):
        callout("info" if i != 4 else "warn", f"{icon} {esc(T(f'about_{i}'))}")
    st.caption("Python · Streamlit · pandas · Plotly · SQLite · fpdf2")

st.markdown(f'<div class="foot">SahiPay · {esc(T("estimate_note"))}<br>App version {esc(APP_VERSION)}</div>',
            unsafe_allow_html=True)
