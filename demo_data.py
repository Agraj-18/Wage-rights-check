"""
demo_data.py  -  SIMULATED entries so the "Group picture" tab has something to show
before real workers have shared anything.

These numbers are MADE UP. The app always labels them as simulated.
"""
import numpy as np
import pandas as pd


def make_demo_entries(industries, state="Tamil Nadu", per_industry=12, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for industry in industries:
        typical_gap = rng.uniform(5, 30)          # a made-up typical shortfall (%)
        for _ in range(per_industry):
            pct = float(np.clip(rng.normal(typical_gap, 10), 0, 60))
            if rng.random() < 0.2:                # some workers are paid fairly
                pct = 0.0
            rows.append({
                "state": state,
                "industry": industry,
                "shortfall_percent": round(pct, 1),
                "source": "SIMULATED",
            })
    return pd.DataFrame(rows)
