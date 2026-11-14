#!/usr/bin/env python3
"""Check the core assumption on today's data: do places with matching climates grow similar crops?

For a random sample of farmed cells, find the best climate match among farmed cells at least
--min-km away (using today's climate for both), and compare crop mixes. The baseline is a
random farmed cell at least as far away. Writes data/validation.json, which the app displays.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from twin import Atlas, haversine


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/atlas.npz")
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--min-km", type=float, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    at = Atlas(a.data)
    rng = np.random.default_rng(a.seed)
    farmed = np.nonzero(at.farmed)[0]
    area = at.crop_area[at.crop_row[farmed]]
    share = area / area.sum(1, keepdims=True)
    top5 = np.argsort(-share, axis=1)[:, :5]
    zf, latf, lonf = at.zcur[farmed], at.lat[farmed], at.lon[farmed]

    def main_crops(i):                     # up to five crops, each with at least 1% of area
        return {k for k in top5[i] if share[i, k] >= 0.01}

    def overlap(i, j):                     # Jaccard overlap: shared crops / all crops in either
        a_, b_ = main_crops(i), main_crops(j)
        return len(a_ & b_) / max(1, len(a_ | b_))

    def cosine(i, j):
        return float(share[i] @ share[j] / (np.linalg.norm(share[i]) * np.linalg.norm(share[j])))

    rows = []
    for i in rng.choice(len(farmed), size=min(a.n, len(farmed)), replace=False):
        ok = np.nonzero(haversine(latf[i], lonf[i], latf, lonf) >= a.min_km)[0]
        if len(ok) == 0:
            continue
        d = np.sqrt(((zf[ok] - zf[i]) ** 2).mean(1))
        j, r = ok[d.argmin()], rng.choice(ok)
        rows.append((float(d.min()), overlap(i, j), overlap(i, r), cosine(i, j), cosine(i, r)))
    r = np.array(rows)
    se = lambda x: float(x.std(ddof=1) / np.sqrt(len(x)))      # noqa: E731
    good = r[:, 0] <= np.median(r[:, 0])
    out = {
        "n": len(r), "min_km": a.min_km, "synthetic": at.synthetic,
        "top5_overlap_twin": round(float(r[:, 1].mean()), 3), "top5_overlap_twin_se": round(se(r[:, 1]), 3),
        "top5_overlap_random": round(float(r[:, 2].mean()), 3), "top5_overlap_random_se": round(se(r[:, 2]), 3),
        "cosine_twin": round(float(r[:, 3].mean()), 3), "cosine_random": round(float(r[:, 4].mean()), 3),
        "top5_overlap_closer_half": round(float(r[good, 1].mean()), 3),
        "top5_overlap_farther_half": round(float(r[~good, 1].mean()), 3),
    }
    path = Path(a.data).with_name("validation.json")
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nMain-crop overlap between climate matches at least {a.min_km:.0f} km apart: "
          f"{out['top5_overlap_twin']:.0%}; between random farmed pairs: {out['top5_overlap_random']:.0%} "
          f"(n={out['n']}, overlap = shared top-5 crops / all top-5 crops in either place).")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
