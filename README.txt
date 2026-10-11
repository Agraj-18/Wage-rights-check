WAGE & RIGHTS CHECKER  -  version 2
===================================

HOW TO RUN
  1. Install Python from python.org (tick "Add Python to PATH").
  2. Open a terminal INSIDE this folder.
     (In VS Code: File > Open Folder, then Terminal > New Terminal.)
  3. Type:   pip install -r requirements.txt
  4. Type:   streamlit run app.py
  5. A web page opens. That is the app.

THE FOUR TABS
  Check my pay        form, answer, "Before you file" guide, letter, "Where to submit"
  Group picture       anonymous results of many workers, put together
  Pay by job (chart)  the lowest legal pay for each job
  About               a simple explanation

FILES
  app.py            the web page
  logic.py          the maths, the letter text, the group summary
  storage.py        saves the anonymous results (SQLite, built into Python)
  demo_data.py      SIMULATED (made-up) entries for the demo
  min_wages.csv     the table of lowest pay (add more rows here)
  requirements.txt  the tools to install
  .streamlit/       the green colour theme (optional)

THE DATA
  min_wages.csv has 8 Tamil Nadu jobs, effective 1 April 2026.
  The numbers came from public websites (WageIndicator), NOT from the
  government paper. CHECK EVERY NUMBER on the official Tamil Nadu Labour
  Department website before the demo.
  Other states and zones are NOT included yet. To add them, add new rows to
  min_wages.csv (keep the column names, and always fill in the "source").

THE GROUP PICTURE
  - A worker can press "Share my result anonymously". Only the date, state,
    job type and the percent / rupees missing are saved. No names.
  - A job is shown only after 5 entries, so nobody can be picked out.
  - The demo data is SIMULATED. The app says so on screen. Turn it off with
    the checkbox, or delete demo_data.py's use in app.py, for the real thing.

PUTTING IT ONLINE (Streamlit Community Cloud)
  Shared results are saved in a file (shared_entries.db). On the free cloud
  this file can be wiped when the app restarts. For the hackathon demo that is
  fine. For real use, a proper online database would be needed.

THINGS NOT TESTED YET
  The logic (maths, letter text, group summary, saving) was tested in plain
  Python. The web page, charts and PDF button need a first run on your computer.
  If you see an error, copy the whole message and ask for help.
