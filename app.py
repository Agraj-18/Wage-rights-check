"""
Wage & Rights Checker  -  the web page (version 3).

Run it with:   streamlit run app.py
"""
import io
import os

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

st.set_page_config(page_title="Wage & Rights Checker", page_icon="₹")

# ---------------------------------------------------------------- language
lang_choice = st.selectbox("🌐 Language / மொழி / भाषा / ಭಾಷೆ / ഭാഷ / భాష", list(LANGS.keys()), key="lang_choice")
lang = LANGS[lang_choice]


def T(key, **kw):
    return t(lang, key, **kw)


# ---------------------------------------------------------------- regional look
# (main colour, second colour) for each state. Simple stripes, like a saree border.
THEMES = {
    "Tamil Nadu": ("#8B1E2D", "#F2A541"), "Kerala": ("#1F6F54", "#D4A537"),
    "Karnataka": ("#B3202A", "#F5C518"), "Andhra Pradesh": ("#1B6E8A", "#F2A541"),
    "Telangana": ("#B83A6B", "#F2A541"), "Maharashtra": ("#C85A0B", "#2E7D5B"),
    "Gujarat": ("#B0175B", "#F2A541"), "Rajasthan": ("#C2452D", "#2A5C8C"),
    "Madhya Pradesh": ("#2A5C8C", "#F2A541"), "Uttar Pradesh": ("#C85A0B", "#1F6F54"),
    "Bihar": ("#8B5A00", "#8B1E2D"), "West Bengal": ("#B3202A", "#FFFFFF"),
    "Odisha": ("#8B5A00", "#8B1E2D"), "Jharkhand": ("#2E7D5B", "#F2A541"),
    "Delhi": ("#1F3A6B", "#F2A541"), "Haryana": ("#2E7D5B", "#F2A541"),
    "Punjab": ("#C85A0B", "#1F3A6B"),
}

CSS = """
<style>
.hero {display:flex; align-items:center; gap:14px; background:PRIMARY; color:#fff;
       padding:14px 16px; border-radius:14px 14px 0 0;}
.hero h1 {margin:0; padding:0; font-size:1.5rem; line-height:1.25; color:#fff;}
.hero p {margin:2px 0 0 0; font-size:1rem; opacity:.95; color:#fff;}
.coin {flex:none; width:46px; height:46px; line-height:46px; text-align:center; border-radius:50%;
       background:ACCENT; color:PRIMARY; font-size:1.5rem; font-weight:700;
       box-shadow:0 0 0 3px rgba(255,255,255,.35);}
.strip {height:12px; border-radius:0 0 14px 14px; margin-bottom:12px;
        background:repeating-linear-gradient(90deg, ACCENT 0 16px, PRIMARY 16px 24px, #ffffff 24px 28px, PRIMARY 28px 36px);}
.stButton > button, .stDownloadButton > button {width:100%; border-radius:10px; font-size:1.05rem;
        padding:.65rem 1rem; border:2px solid PRIMARY;}
[data-testid="stMetricValue"] {font-size:1.5rem;}
div[role="radiogroup"] label {font-size:1.05rem;}
</style>
"""


def inject_style(state):
    primary, accent = THEMES.get(state, THEMES["Tamil Nadu"])
    st.markdown(CSS.replace("PRIMARY", primary).replace("ACCENT", accent), unsafe_allow_html=True)


inject_style(st.session_state.get("sel_state", "Tamil Nadu"))
st.markdown(
    f'<div class="hero"><div class="coin">₹</div><div><h1>{T("title")}</h1><p>{T("tagline")}</p></div></div>'
    '<div class="strip"></div>',
    unsafe_allow_html=True,
)
st.caption(T("estimate_note"))


# ---------------------------------------------------------------- data + helpers

def read_csv_safe(path):
    """
    Read a CSV file even if it was saved in a different text format
    (for example by Excel or Numbers). Tries several encodings.
    If the file is missing or unreadable, returns None instead of crashing.
    """
    if not os.path.exists(path):
        return None
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encodings = ["utf-16"]
    else:
        encodings = ["utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        return None
    try:
        df = pd.read_csv(io.StringIO(text), keep_default_na=False)
    except Exception:
        return None
    df.columns = [str(c).strip() for c in df.columns]
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
    """Show choices as buttons. The last choice lets the worker type a number instead."""
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
    st.subheader(T("letter_title"))
    st.caption(T("letter_caption"))
    worker_name = st.text_input(T("name_label"), key=prefix + "_name")
    employer_name = st.text_input(T("employer_label"), key=prefix + "_employer")
    place = st.text_input(T("place_label"), key=prefix + "_place")
    text = build_letter_text(
        worker_name, employer_name, place, state, job, days, ot_hours, rate_low,
        effective_from, source, paid, result, rate_is_lowest=rate_is_lowest, monthly=monthly,
    )
    st.download_button(T("download_btn"), data=make_pdf(text), file_name="complaint_letter.pdf",
                       mime="application/pdf", key=prefix + "_download")
    with st.expander(T("read_letter")):
        st.text(text)
    with st.expander(T("where_title")):
        st.markdown("\n".join("- " + T(f"where_{i}") for i in range(1, 5)))


def before_you_file():
    st.subheader(T("bf_title"))
    st.info("\n".join("- " + T(f"bf_{i}") for i in range(1, 6)))


data = load_data()

tab_check, tab_proof, tab_group, tab_rights, tab_about = st.tabs(
    [T("tab_check"), T("tab_proof"), T("tab_group"), T("tab_rights"), T("tab_about")]
)

# =====================================================================================
# TAB 1: check my pay  (easy questions, answered with buttons)
# =====================================================================================
with tab_check:
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
        st.info(T("fw_note"))

    st.divider()
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

    period = st.radio(T("q_period"), ["day", "week", "month"], key="pick_period", horizontal=True,
                      format_func=lambda v: T("period_" + v))
    amounts = QUICK_AMOUNTS[period]
    amount_each = float(choice_or_type(T("q_amount"), amounts, "pick_amount_" + period,
                                       lambda v: money(v), T("type_amount"),
                                       0.0, 1000000.0, 9000.0, 100.0, index=min(2, len(amounts) - 1)))
    st.caption(T("include_ot"))
    paid = paid_total(period, amount_each, days)
    st.caption(T("so_you_got", amount=money(paid), days=days))

    lo, hi, verdict = calc_range(rate_low, rate_high, days, ot_hours, paid)

    # ---- the answer
    st.divider()
    a, b, c = st.columns(3)
    a.metric(T("res_should"), money(lo["total_due"]) if exact
             else f"{money(lo['total_due'])} – {money(hi['total_due'])}")
    b.metric(T("res_got"), money(paid))
    if verdict == "under":
        c.metric(T("res_missing"), money(lo["shortfall"]) if exact else "≥ " + money(lo["shortfall"]))
    elif verdict == "fine":
        c.metric(T("res_missing"), money(0))
    else:
        c.metric(T("res_missing"), "?")

    if verdict == "fine":
        st.success(T("msg_fine"))
    elif verdict == "under" and exact:
        st.error(T("msg_under", amount=money(lo["shortfall"])))
    elif verdict == "under":
        st.error(T("msg_atleast", low=money(lo["shortfall"]), high=money(hi["shortfall"])))
    else:
        st.warning(T("msg_unclear"))

    if exact:
        st.caption(T("rate_exact", rate=money2(rate_low)))
    else:
        st.caption(T("rate_range", low=money2(rate_low), high=money2(rate_high)))
    when = f" | {row['effective_from']}" if row["effective_from"] else ""
    st.caption(f"{T('source_label')}: {row['source']}{when}")

    age = rate_age_days(row["effective_from"])
    if conf == "stand_in":
        st.warning(T("warn_standin"))
    elif conf == "disputed":
        st.warning(T("warn_disputed"))
        st.info(T("warn_zone"))
    elif conf == "indicative":
        st.info(T("warn_zone"))
    elif conf == "older" or (age is not None and age > 183):
        st.warning(T("warn_older"))

    with st.expander(T("how_calc")):
        st.write(T("calc_days", rate=money2(rate_low), days=days, amount=money(lo["basic_due"])))
        st.write(T("calc_ot", amount=money(lo["overtime_pay"])))
        st.write(T("calc_total", amount=money(lo["total_due"])))
        st.write(T("calc_missing", due=money(lo["total_due"]), paid=money(paid),
                   amount=money(max(lo["shortfall"], 0))))

    # ---- share without a name
    st.divider()
    st.subheader(T("share_title"))
    st.caption(T("share_caption"))
    can_share = verdict in ("fine", "under") and conf != "stand_in"
    if can_share:
        already = st.session_state.get("shared", False)
        if st.button(T("share_btn"), disabled=already, key="share_button"):
            pct = (lo["shortfall"] / lo["total_due"] * 100) if verdict == "under" else 0.0
            add_entry(state, job, pct, max(lo["shortfall"], 0))
            st.session_state["shared"] = True
            st.success(T("share_thanks"))
    else:
        st.caption(T("share_not_now"))

    # ---- before you file + letter
    if verdict == "under":
        st.divider()
        before_you_file()
        letter_block("single", state, job, days, ot_hours, rate_low, row["effective_from"],
                     row["source"], paid, lo, rate_is_lowest=not exact)

# =====================================================================================
# TAB 2: month by month proof (arrears)
# =====================================================================================
with tab_proof:
    st.subheader(T("proof_title"))
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
        st.info(T("proof_empty"))
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
        x, y, z = st.columns(3)
        x.metric(T("total_due"), money(total_due))
        y.metric(T("total_paid"), money(total_paid))
        z.metric(T("total_arrears"), money(arrears))
        st.caption(T("proof_caveat"))
        st.caption(T("proof_tip"))
        if not exact:
            st.warning(T("warn_disputed"))
        if conf == "stand_in":
            st.warning(T("warn_standin"))

        st.download_button(T("proof_csv"), data=table.to_csv(index=False).encode("utf-8-sig"),
                           file_name="month_by_month_record.csv", mime="text/csv", key="proof_csv")

        if arrears > 0:
            st.divider()
            before_you_file()
            total_result = {"total_due": total_due, "shortfall": arrears,
                            "basic_due": sum(m["basic"] for m in monthly),
                            "overtime_pay": sum(m["ot_pay"] for m in monthly)}
            letter_block("proof", state, job, sum(m["days"] for m in monthly),
                         sum(m["ot_hours"] for m in monthly), rate_low, row["effective_from"],
                         row["source"], total_paid, total_result, rate_is_lowest=not exact,
                         monthly=monthly)
        else:
            st.success(T("proof_fine"))

# =====================================================================================
# TAB 3: group picture (+ lowest pay by job)
# =====================================================================================
with tab_group:
    st.subheader(T("group_title"))
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
        st.info(T("group_empty"))
    else:
        summary, hidden = group_summary(pd.concat(parts, ignore_index=True))
        if summary.empty:
            st.info(T("group_empty"))
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
                         color_discrete_sequence=["#C8553D"], height=max(280, 34 * len(part)))
            st.plotly_chart(fig)
            if use_demo:
                st.warning(T("demo_warning"))
            st.caption(T("group_min", n=MIN_GROUP_SIZE))
            st.caption(T("group_rough"))

    # ---- lowest legal pay by job, for the state chosen in the first tab
    st.divider()
    st.subheader(f"{T('chart_min_title')}: {state_label(lang, state)}")
    shown = state_rows.copy()
    if (shown["rate_low"] == shown["rate_high"]).all():
        shown["label"] = shown["industry"].map(lambda j: job_label(lang, j))
        shown = shown.sort_values("rate_high")
        fig2 = px.bar(shown, x="rate_high", y="label", orientation="h", text="rate_high",
                      labels={"rate_high": T("chart_min_title"), "label": ""},
                      color_discrete_sequence=["#2E7D5B"], height=max(280, 26 * len(shown)))
        st.plotly_chart(fig2)
    else:
        shown["Work"] = shown.apply(
            lambda r: job_label(lang, r["industry"]) + " / " + T("skill_" + r["skill_category"]), axis=1)
        st.dataframe(pd.DataFrame({
            T("col_work"): shown["Work"],
            T("col_low"): shown["rate_low"].round(2),
            T("col_high"): shown["rate_high"].round(2),
        }), hide_index=True)
        st.caption(T("warn_disputed"))
    st.caption(T("chart_min_note"))

# =====================================================================================
# TAB 4: rights & updates (+ WhatsApp channel)
# =====================================================================================
with tab_rights:
    st.subheader(T("channel_title"))
    link = ""
    ch = read_csv_safe("channels.csv")
    if ch is not None and {"language", "invite_link"} <= set(ch.columns):
        found = ch[ch["language"].astype(str).str.strip() == lang]
        if not found.empty:
            link = str(found.iloc[0]["invite_link"]).strip()
    if link:
        st.markdown(f"[{T('channel_join')}]({link})")
    else:
        st.info(T("channel_soon"))

    st.subheader(T("updates_title"))
    ups = read_csv_safe("updates.csv")
    if ups is not None and {"date", "language", "type", "text", "source"} <= set(ups.columns):
        ups = ups[(ups["language"] == lang) | (ups["type"] == "incident")].sort_values("date", ascending=False)
    else:
        ups = pd.DataFrame()
    if ups.empty:
        st.info(T("no_updates"))
    else:
        for _, u in ups.iterrows():
            label = T("incident_label") if u["type"] == "incident" else T("tip_label")
            st.markdown(f"**{label} | {u['date']}**  \n{u['text']}")
            if u["source"]:
                st.caption(f"{T('source_label')}: {u['source']}")
            st.divider()

# =====================================================================================
# TAB 5: about
# =====================================================================================
with tab_about:
    st.subheader(T("tab_about"))
    st.markdown("\n".join("- " + T(f"about_{i}") for i in range(1, 6)))
    st.caption("Python · Streamlit · pandas · Plotly · SQLite · fpdf2")

st.divider()
st.caption(T("estimate_note"))
