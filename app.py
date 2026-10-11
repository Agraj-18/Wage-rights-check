"""
Wage & Rights Checker  -  the web page (version 2).

Run it with:   streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

from logic import (calculate, money, money2, clean_for_pdf, build_letter_text,
                   rate_age_days, group_summary, MIN_GROUP_SIZE)
from storage import add_entry, load_entries
from demo_data import make_demo_entries

# ---------- page settings ----------
st.set_page_config(page_title="Wage & Rights Checker", page_icon="₹")


@st.cache_data
def load_data():
    return pd.read_csv("min_wages.csv")


def make_pdf(text):
    """Turn the letter text into a PDF file (as bytes) that can be downloaded."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in clean_for_pdf(text).split("\n"):
        pdf.multi_cell(0, 7, line if line else " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


data = load_data()

# ---------- title ----------
st.title("₹ Wage & Rights Checker")
st.caption("Know what you're owed.  This is an estimate, not legal advice.")

tab_check, tab_group, tab_chart, tab_about = st.tabs(
    ["Check my pay", "Group picture", "Pay by job (chart)", "About"]
)

# =====================================================
# TAB 1: check my pay
# =====================================================
with tab_check:
    # 1. pick the state and the job
    state = st.selectbox("State", sorted(data["state"].unique()))
    state_data = data[data["state"] == state]
    industry = st.selectbox("Type of work", state_data["industry"].tolist())

    # 2. type the numbers
    col1, col2 = st.columns(2)
    days_worked = col1.number_input("Days worked", min_value=1, max_value=31, value=26)
    overtime_hours = col2.number_input("Overtime hours (total)", min_value=0.0, value=0.0, step=0.5)
    amount_paid = st.number_input("Money you got (Rs)", min_value=0.0, value=9000.0, step=100.0)

    # 3. find the row for this job
    row = state_data[state_data["industry"] == industry].iloc[0]
    rate = float(row["total_per_day"])

    # 4. do the maths (see logic.py)
    result = calculate(rate, days_worked, overtime_hours, amount_paid)

    # 5. show the answer
    st.divider()
    a, b, c = st.columns(3)
    a.metric("You should get", money(result["total_due"]))
    b.metric("You got", money(amount_paid))
    c.metric("Missing", money(max(result["shortfall"], 0)))

    if result["shortfall"] > 0:
        st.error(f"You should get about {money(result['shortfall'])} more.")
    else:
        st.success("Your pay looks fine. You got at least the lowest legal pay.")

    st.caption(
        f"Lowest pay used: {money2(rate)} per day, starting {row['effective_from']}. "
        f"Source: {row['source']}."
    )
    if rate_age_days(row["effective_from"]) > 183:
        st.warning(
            f"This rate started on {row['effective_from']}. Pay rules are changed two times "
            "a year, so please check if there is a newer rate."
        )

    with st.expander("How was this worked out?"):
        st.write(f"Pay for the days: {money2(rate)} × {days_worked} days = {money(result['basic_due'])}")
        st.write(f"Overtime pay: {money(result['overtime_pay'])}")
        st.write(f"Total you should get: {money(result['total_due'])}")
        st.write(f"Missing money: {money(result['total_due'])} − {money(amount_paid)} = {money(result['shortfall'])}")

    # 6. optional: share the result without a name
    st.divider()
    st.subheader("Help other workers (optional)")
    st.caption(
        "You can add your result to the Group picture. Only the type of work and the percent "
        "of pay that was missing are saved. No name, no employer, no place."
    )
    already_shared = st.session_state.get("shared", False)
    if st.button("Share my result anonymously", disabled=already_shared):
        pct = max(result["shortfall"], 0) / result["total_due"] * 100
        add_entry(state, industry, pct, max(result["shortfall"], 0))
        st.session_state["shared"] = True
        st.success("Thank you. Your result was added without your name.")

    # 7. before you file + letter (only if money is missing)
    if result["shortfall"] > 0:
        st.divider()
        st.subheader("Before you file a complaint")
        st.info(
            "Filing is **your choice**, and it can carry a risk. Some employers punish workers "
            "who complain.\n\n"
            "- Try asking for the right pay first, or go **together** with other workers, a union or an NGO.\n"
            "- Ask for free legal advice if you can (for example, the District Legal Services Authority).\n"
            "- **Keep your proof:** attendance, messages, and records of what you were paid.\n"
            "- Do not wait too long. There are time limits (about one year under the older wage law). "
            "Ask the labour office."
        )

        st.subheader("Make a complaint letter")
        st.caption("The letter is made on your screen. Nothing is saved.")
        worker_name = st.text_input("Your name")
        employer_name = st.text_input("Employer / company name")
        place = st.text_input("Your town / district")

        letter_text = build_letter_text(
            worker_name, employer_name, place, state, industry,
            days_worked, overtime_hours, rate,
            row["effective_from"], row["source"], amount_paid, result,
        )
        st.download_button(
            "Download the letter (PDF)",
            data=make_pdf(letter_text),
            file_name="complaint_letter.pdf",
            mime="application/pdf",
        )
        with st.expander("Read the letter"):
            st.text(letter_text)

        with st.expander("Where do I submit it?"):
            st.markdown(
                "- **In person:** the district labour office for the place where the work was done "
                "(ask for the Labour Officer or the Assistant Commissioner of Labour). "
                "Ask for a **stamped copy or receipt** and keep it.\n"
                "- **Online:** the SAMADHAN portal (samadhan.labour.gov.in) or the UMANG app.\n"
                "- To find offices, see the Tamil Nadu Labour Department website (labour.tn.gov.in).\n"
                "- This app does **not** send or file anything for you."
            )

# =====================================================
# TAB 2: group picture
# =====================================================
with tab_group:
    st.subheader("Group picture: how much pay is missing?")
    st.write(
        "Each worker's number is private. Here the numbers of many workers are put together, "
        "so a pattern can be seen without pointing at anyone."
    )
    use_demo = st.checkbox("Include SIMULATED demo data (made-up numbers for the demo)", value=True)

    real = load_entries()
    if not real.empty:
        real = real[["state", "industry", "shortfall_percent"]].copy()
        real["source"] = "Shared by workers"

    parts = [real] if not real.empty else []
    if use_demo:
        parts.append(make_demo_entries(data["industry"].tolist(), state=data["state"].iloc[0]))

    if not parts:
        st.info("Nothing here yet. Share your result in the first tab, or turn on the demo data.")
    else:
        all_entries = pd.concat(parts, ignore_index=True)
        summary, hidden = group_summary(all_entries)
        if summary.empty:
            st.info(f"Not enough entries yet. A job is shown only after {MIN_GROUP_SIZE} entries.")
        else:
            summary = summary.sort_values("avg_missing_percent")
            fig = px.bar(
                summary,
                x="avg_missing_percent",
                y="industry",
                orientation="h",
                text="avg_missing_percent",
                hover_data={"entries": True, "share_underpaid": True},
                labels={"avg_missing_percent": "Average pay missing (%)", "industry": ""},
                color_discrete_sequence=["#C8553D"],
            )
            st.plotly_chart(fig)
            if use_demo:
                st.warning("This chart includes SIMULATED data. The numbers are made up for the demo.")
            st.caption(
                f"A job is shown only when it has at least {MIN_GROUP_SIZE} entries, "
                "so no single worker can be picked out."
            )
            if hidden > 0:
                st.caption(f"{hidden} job(s) are hidden because they have too few entries.")
            st.caption(
                "Anyone can add numbers, so treat this as a rough guide and not as proof."
            )
            with st.expander("See the numbers"):
                st.dataframe(summary.rename(columns={
                    "entries": "Entries",
                    "avg_missing_percent": "Average missing (%)",
                    "share_underpaid": "Share underpaid (%)",
                }))

# =====================================================
# TAB 3: chart of minimum pay by job
# =====================================================
with tab_chart:
    st.subheader(f"Lowest pay per day by job: {state}")
    chart_data = state_data.sort_values("total_per_day")
    fig2 = px.bar(
        chart_data,
        x="total_per_day",
        y="industry",
        orientation="h",
        text="total_per_day",
        labels={"total_per_day": "Lowest pay per day (Rs)", "industry": ""},
        color_discrete_sequence=["#2E7D5B"],
    )
    st.plotly_chart(fig2)

    high = chart_data.iloc[-1]
    low = chart_data.iloc[0]
    ratio = high["total_per_day"] / low["total_per_day"]
    st.info(
        f"{high['industry']} has the highest lowest-pay (Rs {high['total_per_day']:,.0f}). "
        f"{low['industry']} has the lowest (Rs {low['total_per_day']:,.0f}). "
        f"That is about {ratio:.1f} times difference."
    )
    st.caption("This chart shows the lowest legal pay, not what workers really get.")

# =====================================================
# TAB 4: about
# =====================================================
with tab_about:
    st.subheader("What is this?")
    st.write(
        "Many workers get less than the lowest pay the law allows, and they do not know it. "
        "This website checks your pay in a few seconds and tells you how much is missing."
    )
    st.subheader("How it works")
    st.markdown(
        "1. Choose your job and type your days, overtime and the money you got.\n"
        "2. The website finds the lowest legal pay for that job.\n"
        "3. It shows what you should have got and what is missing.\n"
        "4. You can read a short guide on the risks, and download a letter for the labour officer.\n"
        "5. If you want, you can add your result **without your name** to the Group picture."
    )
    st.subheader("Please remember")
    st.markdown(
        "- This is an **estimate**, not legal advice. Check with a labour officer.\n"
        "- We do **not** save your name, your employer or your place.\n"
        "- Nothing is saved unless you press **Share my result anonymously**.\n"
        "- Right now we only have **Tamil Nadu** jobs.\n"
        "- Pay rules change two times a year. Each answer shows where the number came from and its date."
    )
    st.subheader("Built with")
    st.write("Python, Streamlit, pandas, Plotly, SQLite and fpdf2.")

st.divider()
st.caption("Numbers come from public websites. Check them with the official Tamil Nadu Labour Department notification.")
