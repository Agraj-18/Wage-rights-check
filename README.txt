WAGE & RIGHTS CHECKER  -  version 3
===================================

HOW TO RUN
  1. Install Python from python.org (tick "Add Python to PATH").
  2. Open a terminal INSIDE this folder.
     (In VS Code: File > Open Folder, then Terminal > New Terminal.)
  3. Type:   pip install -r requirements.txt
  4. Type:   streamlit run app.py
  5. A web page opens. That is the app.

WHAT IS NEW IN VERSION 3
  - Easy questions: the worker taps choices (days, overtime, how paid, how much).
    If no choice fits, the last button lets them type a number.
  - 6 languages: English, Tamil, Hindi, Kannada, Malayalam, Telugu (first-draft
    translations - ask native speakers to check them).
  - Month by month tab: add a row per month, see the total missing (arrears), download
    the record, and make a letter that lists every month.
  - 17 states. Tamil Nadu has 27 kinds of work, including cracker / fireworks.
    Other states use a range of figures (websites disagree) - see DATA_SOURCES.txt.
  - A regional look (colours and a saree-border stripe that change with the state).
  - Rights & updates tab for the WhatsApp channels.

THE FIVE TABS
  Check my pay     questions, answer, share (no name), before you file, letter
  Month by month   arrears table + letter with all the months
  Group picture    anonymous results of many workers + lowest pay by job
  Rights & updates tips and updates in your language + WhatsApp channel link
  About

FILES
  app.py              the web page
  logic.py            the maths and the letter text
  i18n.py             all the words in 6 languages
  storage.py          saves the anonymous results (SQLite)
  demo_data.py        SIMULATED entries for the demo
  min_wages.csv       the pay table  (see DATA_SOURCES.txt)
  updates.csv         tips and updates (add real daily items here)
  channels.csv        WhatsApp channel links (one per language)
  make_channel_posts.py   makes ready-to-paste channel posts from updates.csv
  requirements.txt    the tools to install
  .streamlit/         the colour theme

WHATSAPP CHANNELS (this part is manual)
  WhatsApp channels can only be created inside the WhatsApp app. A channel has one
  language, so make ONE channel per language (6 channels):
    1. In WhatsApp: Updates tab > "+" > New channel.
    2. Name it like the name in channels.csv, and copy its invite link.
    3. Paste each link into channels.csv (column invite_link). The app then shows a
       "Join" link in that language.
    4. Add real, dated, sourced items to updates.csv every day (type "incident" or "tip").
    5. Run:  python make_channel_posts.py   then copy each post from the
       channel_posts folder into the matching channel.
  The one "incident" in updates.csv is only a SAMPLE. Replace it with real items.

THINGS TO KNOW
  - The PDF letter is in ENGLISH only, and names must be typed in English letters
    (the PDF font cannot show Indian scripts yet).
  - Shared results are saved in shared_entries.db. On free online hosting this file
    can be wiped when the app restarts. That is fine for a demo.
  - The logic, the text in all 6 languages and every state/job were tested with a
    pretend Streamlit. The real page, the charts and the PDF button still need a first
    run on your computer. If you see an error, copy the whole message and ask for help.
