#!/usr/bin/env python3
"""Write a SYNTHETIC data/atlas.npz so the app can be developed before the real download ends.

The numbers are invented (temperature from latitude, made-up rain and crops). The app shows a
red banner while this file is loaded. Never demo or report results from it.
"""
from pathlib import Path

import numpy as np

H, W, RES = 1080, 2160, 1 / 6
rng = np.random.default_rng(0)
lat = 90 - (np.arange(H) + 0.5) * RES
lon = -180 + (np.arange(W) + 0.5) * RES
LAT, LON = np.meshgrid(lat, lon, indexing="ij")
land = (LAT > -55) & (LAT < 70) & (np.sin(np.radians(LON * 2.5)) + np.cos(np.radians(LAT * 4)) > -0.6)
rows, cols = np.nonzero(land)
la, lo = LAT[rows, cols], LON[rows, cols]

t = 28 - 0.55 * np.abs(la) + 3 * np.sin(np.radians(lo * 3))
rain = np.clip(1800 * np.exp(-((np.abs(la) - 5) / 18) ** 2) + 700 * np.exp(-((np.abs(la) - 50) / 12) ** 2)
               + 250 * np.sin(np.radians(lo * 4)), 20, None)
season = np.clip(90 - np.abs(la) * 1.2, 10, None)
cur = np.stack([t, t + 8 + np.abs(la) * 0.15, t - 8 - np.abs(la) * 0.3, rain, season,
                rain * 0.4, rain * 0.15], 1).astype(np.float32)


def future(dt, dr):
    f = cur.copy()
    f[:, :3] += dt
    f[:, [3, 5, 6]] *= dr
    return f


codes = ["whea", "maiz", "rice", "sorg", "cass", "barl", "soyb", "cott", "pmil", "pota"]
opt_t = np.array([14, 22, 26, 27, 26, 9, 21, 25, 29, 11])
opt_r = np.array([550, 800, 1500, 500, 1300, 450, 900, 650, 350, 700])
fit = np.exp(-((t[:, None] - opt_t) / 5) ** 2 - ((np.sqrt(rain)[:, None] - np.sqrt(opt_r)) / 6) ** 2)
area = (fit * 9000 * rng.uniform(0.5, 1.5, fit.shape)).astype(np.float32)
area[area < 150] = 0
has = area.sum(1) > 0

out = Path("data/atlas.npz")
out.parent.mkdir(exist_ok=True)
np.savez_compressed(
    out, rows=rows.astype(np.int16), cols=cols.astype(np.int16),
    vars=np.array(["bio1", "bio5", "bio6", "bio12", "bio15", "bio18", "bio19"]), cur=cur,
    periods=np.array(["2021-2040", "2041-2060"]),
    **{"fut_2021-2040": future(1.0, 0.97), "fut_2041-2060": future(2.0, 0.94)},
    models=np.array(["SYNTHETIC"]), ssp=np.array("none"),
    crop_cells=np.nonzero(has)[0].astype(np.int32), crop_area=area[has],
    crop_irr=(area[has].sum(1) * rng.uniform(0, 0.4, int(has.sum()))).astype(np.float32),
    crop_codes=np.array(codes), synthetic=np.array(True))
print(f"wrote {out} (SYNTHETIC test data, {len(rows):,} cells)")
