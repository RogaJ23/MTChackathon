"""Climate-twin engine: find places whose climate today matches a farm's projected climate."""
import math
from pathlib import Path

import numpy as np

RES = 1 / 6
H, W = 1080, 2160

# name shown to users, unit, decimals
VAR_INFO = {
    "bio1": ("Average temperature", "°C", 1),
    "bio5": ("Hottest-month daytime high", "°C", 1),
    "bio6": ("Coldest-month night-time low", "°C", 1),
    "bio12": ("Rain per year", "mm", 0),
    "bio15": ("Rainfall seasonality (0 = even)", "", 0),
    "bio18": ("Rain in the warmest 3 months", "mm", 0),
    "bio19": ("Rain in the coldest 3 months", "mm", 0),
}
SQRT_VARS = {"bio12", "bio18", "bio19"}     # rainfall is compared on a square-root scale

CROP_NAMES = {
    "whea": "Wheat", "rice": "Rice", "maiz": "Maize", "barl": "Barley",
    "pmil": "Pearl millet", "smil": "Small millet", "mill": "Millet", "sorg": "Sorghum",
    "ocer": "Other cereals", "pota": "Potato", "swpo": "Sweet potato", "yams": "Yams",
    "cass": "Cassava", "orts": "Other roots", "bean": "Beans", "chic": "Chickpea",
    "cowp": "Cowpea", "pige": "Pigeon pea", "lent": "Lentil", "opul": "Other pulses",
    "soyb": "Soybean", "grou": "Groundnut", "cnut": "Coconut", "oilp": "Oil palm",
    "sunf": "Sunflower", "rape": "Rapeseed", "sesa": "Sesame", "ooil": "Other oil crops",
    "sugc": "Sugarcane", "sugb": "Sugar beet", "cott": "Cotton", "ofib": "Other fibre crops",
    "acof": "Arabica coffee", "rcof": "Robusta coffee", "coff": "Coffee", "coco": "Cocoa",
    "teas": "Tea", "toba": "Tobacco", "bana": "Banana", "plnt": "Plantain",
    "trof": "Tropical fruit", "temf": "Temperate fruit", "vege": "Vegetables",
    "citr": "Citrus", "onio": "Onion", "toma": "Tomato", "rubb": "Rubber",
    "rest": "Other crops",
}
GENERIC = {"rest"}        # too vague to recommend

PRESENT = 0.03            # a crop "is grown" in a place if it has >= 3% of harvested area
ABSENT = 0.01             # ... and "is not grown" below 1%
FARMED_FRACTION = 0.01    # a cell counts as farmed if >= 1% of its area is harvested
NEAR_KM = 50              # radius used for "crops near the farm"
CLOSE, PARTIAL = 0.35, 0.70   # climate-distance cut-offs (judgement calls; see README)

PERIOD_LABELS = {
    "2021-2040": "around 2030 (2021–2040 average)",
    "mid": "around 2040 (2021–2060 average)",
    "2041-2060": "around 2050 (2041–2060 average)",
}


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compass(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((math.degrees(math.atan2(y, x)) + 382.5) % 360 // 45)]


class Atlas:
    def __init__(self, path="data/atlas.npz"):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run build_data.py (or make_demo_data.py) first.")
        z = np.load(path)
        self.vars = [str(v) for v in z["vars"]]
        self.rows, self.cols = z["rows"].astype(int), z["cols"].astype(int)
        self.lat = 90 - (self.rows + 0.5) * RES
        self.lon = -180 + (self.cols + 0.5) * RES
        self.n = len(self.rows)
        self.cur = z["cur"]
        raw_periods = [str(p) for p in z["periods"]]
        self.fut = {p: z[f"fut_{p}"] for p in raw_periods}
        if {"2021-2040", "2041-2060"} <= set(raw_periods):
            self.fut["mid"] = (self.fut["2021-2040"] + self.fut["2041-2060"]) / 2
        self.periods = [p for p in PERIOD_LABELS if p in self.fut]
        self.models = [str(m) for m in z["models"]]
        self.ssp = str(z["ssp"])
        self.synthetic = bool(z["synthetic"])

        self.grid = np.full((H, W), -1, np.int32)
        self.grid[self.rows, self.cols] = np.arange(self.n)

        self._sqrt = np.array([v in SQRT_VARS for v in self.vars])
        self.scale = self._t(self.cur).std(axis=0)
        self.scale[self.scale == 0] = 1
        self.zcur = (self._t(self.cur) / self.scale).astype(np.float32)

        self.codes = [str(c) for c in z["crop_codes"]]
        self.crop_names = [CROP_NAMES.get(c, c.upper()) for c in self.codes]
        self.crop_area = z["crop_area"]
        self.crop_irr = z["crop_irr"]
        self.crop_row = np.full(self.n, -1, np.int32)
        self.crop_row[z["crop_cells"]] = np.arange(len(z["crop_cells"]))
        total = np.zeros(self.n, np.float32)
        total[z["crop_cells"]] = self.crop_area.sum(1)
        cell_ha = 34422.0 * np.cos(np.radians(self.lat))
        self.farmed = total >= FARMED_FRACTION * cell_ha

    # ------------------------------------------------------------- helpers
    def _t(self, x):
        x = np.asarray(x, np.float64)
        return np.where(self._sqrt, np.sqrt(np.clip(x, 0, None)), x)

    def z(self, x):
        return (self._t(x) / self.scale).astype(np.float32)

    def cell_at(self, lat, lon):
        lon = (lon + 180) % 360 - 180
        r = min(H - 1, max(0, int((90 - lat) / RES)))
        c = min(W - 1, max(0, int((lon + 180) / RES)))
        i = int(self.grid[r, c])
        if i >= 0:
            return i
        d = haversine(lat, lon, self.lat, self.lon)
        i = int(d.argmin())
        if d[i] > 150:
            raise ValueError("No land climate data at this point. Click on land.")
        return i

    def climate(self, values):
        return {v: round(float(x), VAR_INFO[v][2] if v in VAR_INFO else 1)
                for v, x in zip(self.vars, values)}

    def crop_mix(self, cells, top=6):
        rows = self.crop_row[cells]
        rows = rows[rows >= 0]
        if len(rows) == 0:
            return None, 0.0, []
        sums = self.crop_area[rows].sum(0)
        total = float(sums.sum())
        if total <= 0:
            return None, 0.0, []
        share = sums / total
        irr = float(min(1.0, self.crop_irr[rows].sum() / total))
        order = np.argsort(-share)[:top]
        listing = [{"code": self.codes[k], "name": self.crop_names[k], "share": round(float(share[k]), 3)}
                   for k in order if share[k] >= 0.005]
        return share, irr, listing

    # --------------------------------------------------------------- query
    def query(self, lat, lon, period="mid", n_twins=5, min_km=100, sep_km=500, top_m=3000):
        if period not in self.fut:
            raise ValueError(f"unknown period {period}")
        i = self.cell_at(lat, lon)
        flat, flon = float(self.lat[i]), float(self.lon[i])
        target = self.fut[period][i]
        d = np.sqrt(((self.zcur - self.z(target)) ** 2).mean(axis=1))
        shift = float(d[i])
        km = haversine(flat, flon, self.lat, self.lon)
        far = km >= min_km
        notes = []

        farm_share, farm_irr, farm_crops = self.crop_mix(np.nonzero(km <= NEAR_KM)[0])
        if farm_share is None:
            notes.append(f"The crop maps show no cropland within {NEAR_KM} km of this point, "
                         "so the comparison with local crops is empty.")

        best_any = float(d[far].min()) if far.any() else None
        cand = np.nonzero(far & self.farmed)[0]
        twins, matches = [], []
        if len(cand):
            m = min(top_m, len(cand))
            order = cand[np.argpartition(d[cand], m - 1)[:m]]
            order = order[np.argsort(d[order])]
            assigned = np.full(m, -1)
            for t in range(n_twins):
                free = np.nonzero(assigned < 0)[0]
                if len(free) == 0:
                    break
                c = order[free[0]]
                if twins and d[c] > PARTIAL:
                    break                      # only the best twin is shown when matches are poor
                near = haversine(self.lat[c], self.lon[c], self.lat[order[free]], self.lon[order[free]]) <= sep_km
                members = free[near]
                assigned[members] = t
                share, irr, crops = self.crop_mix(order[members])
                dist = float(d[c])
                twins.append({
                    "rank": t + 1, "lat": round(float(self.lat[c]), 3), "lon": round(float(self.lon[c]), 3),
                    "distance_km": int(round(float(km[c]))),
                    "direction": compass(flat, flon, float(self.lat[c]), float(self.lon[c])),
                    "climate_distance": round(dist, 3),
                    "quality": "close" if dist <= CLOSE else "partial" if dist <= PARTIAL else "poor",
                    "n_cells": int(len(members)), "today": self.climate(self.cur[c]),
                    "crops": crops, "irrigated_share": round(irr, 2), "_share": share,
                })
            keep = np.nonzero(assigned >= 0)[0][:1500]
            matches = [[round(float(self.lat[order[k]]), 2), round(float(self.lon[order[k]]), 2),
                        round(float(d[order[k]]), 3), int(assigned[k])] for k in keep]
            if best_any is not None and twins and twins[0]["climate_distance"] > max(CLOSE, best_any + 0.25):
                notes.append("The closest matches to this future climate are places that are not farmed today. "
                             "The twins shown are the nearest farmed matches, which fit less well.")
        else:
            notes.append("No farmed region was found to compare against.")

        advice = self._advice(farm_share, [t for t in twins if t["quality"] != "poor"])
        if twins and not advice["used"]:
            notes.append("No region today is a good match for this future climate, so no crop suggestions are made.")
        for t in twins:
            t.pop("_share")
        return {
            "farm": {"lat": round(lat, 4), "lon": round(lon, 4), "cell_lat": round(flat, 3), "cell_lon": round(flon, 3),
                     "today": self.climate(self.cur[i]), "future": self.climate(target),
                     "crops": farm_crops, "irrigated_share": round(farm_irr, 2)},
            "period": period, "period_label": PERIOD_LABELS[period],
            "shift": round(shift, 3), "best_any": None if best_any is None else round(best_any, 3),
            "twins": twins, "advice": advice, "matches": matches, "notes": notes,
        }

    def _advice(self, farm_share, twins):
        out = {"try": [], "keep": [], "watch": [], "used": len(twins)}
        if not twins:
            return out
        n = len(twins)
        shares = np.array([t["_share"] for t in twins])          # (n, C)
        count = (shares >= PRESENT).sum(0)
        mean = shares.mean(0)
        farm = farm_share if farm_share is not None else np.zeros(len(self.codes))
        for k in np.argsort(-(count + mean)):
            if self.codes[k] in GENERIC:
                continue
            item = {"name": self.crop_names[k], "twins": int(count[k]), "of": n,
                    "twin_share": round(float(mean[k]), 3), "farm_share": round(float(farm[k]), 3)}
            support = count[k] / n
            if farm[k] >= PRESENT:
                out["keep" if support >= 0.4 else "watch"].append(item)
            elif farm[k] < ABSENT and support >= 0.4:
                out["try"].append(item)
        return out
