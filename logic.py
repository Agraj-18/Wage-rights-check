"""
logic.py  -  the "brain" of the app (plain Python, no web page stuff).

Keeping the maths here, away from the web page, makes it easy to test.
"""
import re
import unicodedata
from datetime import date, datetime

import pandas as pd

# ---- Rules we ASSUME. Check these against the official rules before the demo! ----
NORMAL_HOURS_PER_DAY = 8      # a normal working day
OVERTIME_MULTIPLIER = 2       # overtime is paid double
WORKING_DAYS_PER_MONTH = 26   # used to turn a monthly rate into a daily rate

MIN_GROUP_SIZE = 5            # groups smaller than this are hidden


# ---------------- money formatting ----------------

def indian(n):
    """1234567 -> '12,34,567' (Indian digit grouping)."""
    n = int(round(n))
    s = str(abs(n))
    if len(s) <= 3:
        out = s
    else:
        last3, rest = s[-3:], s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        out = ",".join(parts + [last3])
    return ("-" if n < 0 else "") + out


def money(amount):
    """On screen:  ₹4,139"""
    return "₹" + indian(amount)


def money2(amount):
    """On screen, with paise (for daily rates):  ₹505.34"""
    return f"₹{amount:,.2f}"


def money_pdf(amount):
    """In the PDF letter (the basic PDF font has no rupee sign):  Rs 4,139"""
    return "Rs " + indian(amount)


def clean_for_pdf(text):
    """The basic PDF font only knows simple letters, so replace anything unusual."""
    return (text.replace("\u2013", "-").replace("\u2014", "-")
            .replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .encode("latin-1", "replace").decode("latin-1"))


# ---------------- the maths ----------------

def calculate(rate_per_day, days_worked, overtime_hours, amount_paid):
    """Work out how much the worker should have got, and how much is missing."""
    basic_due = rate_per_day * days_worked
    hourly_rate = rate_per_day / NORMAL_HOURS_PER_DAY
    overtime_pay = overtime_hours * hourly_rate * OVERTIME_MULTIPLIER
    total_due = basic_due + overtime_pay
    shortfall = total_due - amount_paid
    return {
        "basic_due": basic_due,
        "overtime_pay": overtime_pay,
        "total_due": total_due,
        "shortfall": shortfall,
    }


def calc_range(rate_low, rate_high, days_worked, overtime_hours, amount_paid):
    """
    Some states have only a range of figures (websites disagree).
    We work out the result for the LOWEST and the HIGHEST figure.
    Returns (low_result, high_result, verdict) where verdict is:
      'fine'    - paid at least the highest figure
      'under'   - paid less than the lowest figure (so underpaid whichever figure is right)
      'unclear' - paid between the two figures
    """
    lo = calculate(rate_low, days_worked, overtime_hours, amount_paid)
    hi = calculate(rate_high, days_worked, overtime_hours, amount_paid)
    if amount_paid >= hi["total_due"]:
        verdict = "fine"
    elif amount_paid < lo["total_due"]:
        verdict = "under"
    else:
        verdict = "unclear"
    return lo, hi, verdict


def paid_total(period, amount_each, days_worked):
    """
    Turn 'I get Rs X every day / week / month' into the total money received.
    daily:   X x days        weekly: X x (days / 6)        monthly: X
    """
    if period == "day":
        return amount_each * days_worked
    if period == "week":
        return amount_each * (days_worked / 6.0)
    return amount_each


QUICK_AMOUNTS = {
    "day": [200, 250, 300, 350, 400, 450, 500, 600],
    "week": [1500, 2000, 2500, 3000, 3500, 4000],
    "month": [6000, 8000, 9000, 10000, 12000, 14000, 16000],
}
QUICK_DAYS = [10, 15, 20, 22, 24, 26, 28, 30]

# extra hours per working day for the quick choices
OVERTIME_CHOICES = {"none": 0.0, "low": 1.5, "high": 3.5}


def rate_age_days(effective_from, today=None):
    """How many days ago did this rate start? Returns None if the date is not known."""
    if effective_from is None or str(effective_from).strip() in ("", "nan", "NaT"):
        return None
    today = today or date.today()
    start = datetime.strptime(str(effective_from), "%Y-%m-%d").date()
    return (today - start).days


# ---------------- the letter ----------------

def build_letter_text(worker_name, employer_name, place, state, industry,
                      days_worked, overtime_hours, rate_per_day,
                      effective_from, source, amount_paid, result,
                      rate_is_lowest=False, monthly=None):
    """Write the complaint letter as plain English text (the PDF is English only)."""
    worker_name = worker_name.strip() or "(your name)"
    employer_name = employer_name.strip() or "(employer name)"
    place = place.strip() or "(place / district)"
    today = date.today().strftime("%d %B %Y")

    when = f"rate effective from {effective_from}; " if str(effective_from) not in ("", "nan", "None") else ""
    if rate_is_lowest:
        rate_line = (f"According to the figures I could find, the minimum wage for this work is at least "
                     f"Rs {rate_per_day:,.2f} per day ({when}source: {source}).")
    else:
        rate_line = (f"The minimum wage for this work is {rate_per_day:,.2f} rupees per day "
                     f"({when}source: {source}).")

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
        f"I, {worker_name}, worked for {employer_name} in the following work: {industry}.",
        "",
        rate_line,
        "",
    ]

    if monthly:
        lines.append("Month by month record:")
        for m in monthly:
            lines.append(
                f"- {m['month'] or '(month)'}: {m['days']} days"
                + (f", {m['ot_hours']:g} extra hours" if m["ot_hours"] > 0 else "")
                + f". Should have received {money_pdf(m['due'])}, received {money_pdf(m['paid'])}, "
                  f"unpaid {money_pdf(max(m['missing'], 0))}."
            )
        lines += [
            "",
            f"In total I should have received {money_pdf(result['total_due'])}, "
            f"but I received {money_pdf(amount_paid)}.",
            f"The total unpaid amount (arrears) is about {money_pdf(result['shortfall'])}.",
        ]
    else:
        lines += [
            f"I worked {days_worked} days"
            + (f" and {overtime_hours:g} extra hours." if overtime_hours > 0 else "."),
            f"By this rate, I should have received {money_pdf(result['total_due'])}. "
            f"I was paid only {money_pdf(amount_paid)}.",
            f"The amount still unpaid is about {money_pdf(result['shortfall'])}.",
        ]

    lines += [
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
        "Note: This letter was prepared with SahiPay. The amounts "
        "are estimates and should be checked against the official notification.",
    ]
    return "\n".join(lines)


# ---------------- group picture ----------------

def group_summary(entries, min_group=MIN_GROUP_SIZE):
    """
    Turn many anonymous entries into one line per job: how many entries, the average
    % missing, and the share of workers who were underpaid. Jobs with fewer than
    min_group entries are hidden. Returns (table_to_show, number_of_hidden_jobs).
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


# ---------------- voice: turn what the worker SAYS into a number ----------------
_ENGLISH_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_MULT = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lac": 100000}
# words that mean "thousand / lakh / hundred" in the six languages (used after a spoken digit, e.g. "9 thousand")
_THOUSAND = ("thousand", "हज़ार", "हजार", "ஆயிரம்", "ஆயிரம", "ಸಾವಿರ", "ആയിരം", "వెయ్యి", "వేల")
_LAKH = ("lakh", "lac", "लाख", "லட்சம்", "லட்ச", "ಲಕ್ಷ", "ലക്ഷം", "లక్ష")
_HUNDRED = ("hundred", "सौ", "நூறு", "ನೂರು", "നൂറ്", "వంద")
_ZERO_WORDS = ("zero", "none", "nothing", "nil", "no ", "नहीं", "नही", "शून्य", "जीरो", "इंपॉसिबल",
               "இல்லை", "பூஜ்ஜியம்", "சுழியம்", "లేదు", "సున్నా", "ಇಲ್ಲ", "ಸೊನ್ನೆ", "ഇല്ല", "പൂജ്യം")


def _ascii_digits(text):
    """Turn Tamil, Hindi, Telugu, Kannada and Malayalam digits into 0-9."""
    out = []
    for ch in text:
        try:
            out.append(str(unicodedata.digit(ch)) if not ch.isascii() else ch)
        except (TypeError, ValueError):
            out.append(ch)
    return "".join(out)


def parse_number(text):
    """
    Find the number in what the worker said. Returns a number, or None if there is none.
    Understands: digits ("26", "9,000", "९०००"), "9 thousand" / "9 हज़ार", English words
    ("twenty six", "nine thousand five hundred"), and "none / no / नहीं / இல்லை..." as zero.
    """
    if text is None:
        return None
    t = _ascii_digits(str(text)).lower().strip()
    if not t:
        return None
    # 1. digits (with optional commas and decimals)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", t)
    if m:
        value = float(m.group(0).replace(",", ""))
        rest = t[m.end():]
        if any(w in rest for w in _LAKH):
            value *= 100000
        elif any(w in rest for w in _THOUSAND):
            value *= 1000
        elif any(w in rest for w in _HUNDRED):
            value *= 100
        return int(value) if float(value).is_integer() else value
    # 2. English number words
    tokens = re.findall(r"[a-z]+", t.replace("-", " "))
    total, current, found = 0, 0, False
    for tok in tokens:
        if tok in _ENGLISH_WORDS:
            current += _ENGLISH_WORDS[tok]; found = True
        elif tok in _MULT:
            found = True
            if tok == "hundred":
                current = max(current, 1) * 100
            else:
                total += max(current, 1) * _MULT[tok]; current = 0
    if found:
        return total + current
    # 3. "none / no" in any of the six languages means zero
    if any(w in (t + " ") for w in _ZERO_WORDS):
        return 0
    return None


# ---------------- voice: match what the worker SAYS to one of the choices ----------------
import difflib


def _norm(text):
    """lower case, no spaces or punctuation (works for Indian scripts too)."""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return "".join(ch for ch in text if ch.isalnum() or unicodedata.category(ch).startswith("M"))


def _tokens(label):
    parts = re.split(r"[\s/,()\-]+", unicodedata.normalize("NFKC", str(label)).lower())
    return [_norm(p) for p in parts if len(_norm(p)) >= 3]


def match_choice(heard, candidates, threshold=0.6):
    """
    heard      what the worker said (text)
    candidates a list of (value, [names the worker might say, in any language])
    Returns (value, score) for the best match, or (None, score) when there is no clear winner.
    """
    h = _norm(heard)
    if len(h) < 2:
        return None, 0.0
    scored = []
    for value, labels in candidates:
        best = 0.0
        for label in labels:
            n = _norm(label)
            if not n:
                continue
            if h == n:
                best = max(best, 1.0)
            elif len(h) >= 3 and (h in n or n in h):
                best = max(best, 0.9)                       # said the whole name, or a clear part of it
            for tok in _tokens(label):
                if len(h) >= 3 and (h == tok or h in tok or tok in h):
                    best = max(best, 0.85)                  # said one of the words in the name
            best = max(best, difflib.SequenceMatcher(None, h, n).ratio())
        scored.append((best, value))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_value = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if top_score < threshold:
        return None, top_score
    if top_score < 0.95 and (top_score - second) < 0.04:
        return None, top_score                              # two choices look equally good: do not guess
    return top_value, top_score
