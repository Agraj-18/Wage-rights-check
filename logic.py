"""
logic.py  -  the "brain" of the app (plain Python, no web page stuff).

Keeping the maths here, away from the web page, makes it easy to test.
"""
from datetime import date, datetime

import pandas as pd

# ---- Rules we ASSUME. Check these against the official rules before the demo! ----
NORMAL_HOURS_PER_DAY = 8      # a normal working day
OVERTIME_MULTIPLIER = 2       # overtime is paid double


def calculate(rate_per_day, days_worked, overtime_hours, amount_paid):
    """Work out how much the worker should have got, and how much is missing."""
    basic_due = rate_per_day * days_worked                       # lowest pay x days
    hourly_rate = rate_per_day / NORMAL_HOURS_PER_DAY            # pay for one hour
    overtime_pay = overtime_hours * hourly_rate * OVERTIME_MULTIPLIER
    total_due = basic_due + overtime_pay                         # what he SHOULD get
    shortfall = total_due - amount_paid                          # missing money
    return {
        "basic_due": basic_due,
        "overtime_pay": overtime_pay,
        "total_due": total_due,
        "shortfall": shortfall,
    }


def money(amount):
    """Write a number like 4138.84 as 'Rs 4,139'."""
    return f"Rs {amount:,.0f}"


def money2(amount):
    """Same as money(), but with paise, for per-day rates: 'Rs 505.34'."""
    return f"Rs {amount:,.2f}"


def clean_for_pdf(text):
    """The basic PDF font only knows simple letters, so replace anything unusual."""
    return text.encode("latin-1", "replace").decode("latin-1")


def build_letter_text(worker_name, employer_name, place, state, industry,
                      days_worked, overtime_hours, rate_per_day,
                      effective_from, source, amount_paid, result):
    """Write the complaint letter as plain text."""
    worker_name = worker_name.strip() or "(your name)"
    employer_name = employer_name.strip() or "(employer name)"
    place = place.strip() or "(place / district)"
    today = date.today().strftime("%d %B %Y")

    lines = [
        f"Date: {today}",
        "",
        "To,",
        "The Labour Officer / Assistant Commissioner of Labour",
        f"{place}, {state}",
        "",
        "Subject: Complaint about payment of less than the minimum wage",
        "",
        "Respected Sir/Madam,",
        "",
        f"I, {worker_name}, worked for {employer_name} in the {industry} "
        f"for {days_worked} days"
        + (f" and {overtime_hours:g} overtime hours." if overtime_hours > 0 else "."),
        "",
        f"The minimum wage for this work is {money2(rate_per_day)} per day "
        f"(rate effective from {effective_from}; source: {source}).",
        "",
        f"By this rate, I should have received {money(result['total_due'])}. "
        f"I was paid only {money(amount_paid)}.",
        "",
        f"The amount still unpaid is about {money(result['shortfall'])}.",
        "",
        "I request you to please look into this matter and help me get the "
        "remaining wages that are due to me.",
        "",
        "Thank you.",
        "",
        "Yours faithfully,",
        worker_name,
        "",
        "-----",
        "Note: This letter was prepared with the Wage & Rights Checker. The amounts "
        "are estimates and should be checked against the official notification.",
    ]
    return "\n".join(lines)


# ---------------- extra helpers (version 2) ----------------

MIN_GROUP_SIZE = 5   # groups smaller than this are hidden, so nobody can be identified


def rate_age_days(effective_from, today=None):
    """How many days ago did this pay rate start? (effective_from looks like '2026-04-01')"""
    today = today or date.today()
    start = datetime.strptime(str(effective_from), "%Y-%m-%d").date()
    return (today - start).days


def group_summary(entries, min_group=MIN_GROUP_SIZE):
    """
    Turn many anonymous entries into one line per job:
    how many entries, the average % missing, and the share of workers who were underpaid.
    Jobs with fewer than min_group entries are hidden.
    Returns (table_to_show, number_of_hidden_jobs).
    """
    if entries.empty:
        return entries, 0
    grouped = (
        entries.groupby(["state", "industry"])["shortfall_percent"]
        .agg(
            entries="size",
            avg_missing_percent="mean",
            share_underpaid=lambda s: (s > 0).mean() * 100,
        )
        .reset_index()
    )
    shown = grouped[grouped["entries"] >= min_group].copy()
    hidden = len(grouped) - len(shown)
    shown["avg_missing_percent"] = shown["avg_missing_percent"].round(1)
    shown["share_underpaid"] = shown["share_underpaid"].round(0)
    return shown, hidden
