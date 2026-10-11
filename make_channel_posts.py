"""
make_channel_posts.py  -  turns updates.csv into ready-to-paste WhatsApp channel posts.

Run:   python make_channel_posts.py
It creates a folder  channel_posts/  with one text file per language.
You then copy each post and paste it into the matching WhatsApp channel.

WhatsApp channels can only be created and posted to from the WhatsApp app itself,
so this step is manual. Use ONE channel per language.
"""
import os

import pandas as pd

LANG_NAME = {"en": "English", "ta": "Tamil", "hi": "Hindi", "kn": "Kannada", "ml": "Malayalam", "te": "Telugu"}
HEADER = {
    "en": "Wage & Rights Update", "ta": "ஊதிய உரிமை செய்தி", "hi": "वेतन अधिकार अपडेट",
    "kn": "ವೇತನ ಹಕ್ಕು ಸುದ್ದಿ", "ml": "വേതന അവകാശ വാർത്ത", "te": "వేతన హక్కుల అప్‌డేట్",
}

updates = pd.read_csv("updates.csv", keep_default_na=False)
os.makedirs("channel_posts", exist_ok=True)

for code, name in LANG_NAME.items():
    # tips in that language, plus incidents (English only) for every channel
    rows = updates[(updates["language"] == code) | (updates["type"] == "incident")]
    rows = rows.sort_values("date", ascending=False)
    posts = []
    for _, r in rows.iterrows():
        post = f"*{HEADER[code]}* - {r['date']}\n\n{r['text']}"
        if r["source"]:
            post += f"\n\nSource: {r['source']}"
        posts.append(post)
    with open(os.path.join("channel_posts", f"{name}.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n==========\n\n".join(posts))
    print(f"{name}: {len(posts)} posts")
