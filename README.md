# Climate Twin Crop Advisor

Agricultural resilience track.

Pick any farm on a map. The tool finds the places whose climate **today** matches that farm's
**projected** climate (around 2030, 2040 or 2050) and shows which crops are grown there. A farmer
gets a concrete answer ("your 2040 looks like region X today, where they grow sorghum and
groundnut") instead of a temperature forecast.

## What it does

1. Looks up the farm's climate today and its projected climate (seven temperature and rainfall measures).
2. Compares that projected climate with today's climate in every farmed 10 arc-minute cell on Earth (about 18 km at the equator).
3. Groups the best matches into up to five "twin" regions at least 500 km apart from each other.
4. Compares the crops grown in the twins with the crops grown within 50 km of the farm, and sorts them into:
   - **candidates to trial**: grown in the twins, not grown near the farm
   - **likely still suited**: grown near the farm and in the twins
   - **worth watching**: grown near the farm but rare in the twins
5. Says so plainly when no farmed region today is a good match (a "novel" climate) and withholds crop suggestions.

## How to run

Tested with Python 3.13. Needs internet for the one-time data download and for map tiles.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# one-time: download about 400 MB of public data and build data/atlas.npz (resumable)
.venv/bin/python build_data.py
#   smaller and faster (one climate model, about 250 MB):
#   .venv/bin/python build_data.py --models MPI-ESM1-2-HR
#   If the crop maps cannot be downloaded automatically, the script prints what to do:
#   download spam2010v2r0_global_harv_area.geotiff.zip from https://doi.org/10.7910/DVN/PRFF8V
#   into your Downloads folder and run the script again.

# optional but recommended: run the check described below; the app displays the result
.venv/bin/python evaluate.py

.venv/bin/python app.py        # then open http://localhost:8000
```

To work on the interface before the download finishes, `python make_demo_data.py` writes an
invented dataset. The app shows a red "synthetic test data" banner while it is loaded. Do not
demo or report anything from it.

## Files

| File | Purpose |
|---|---|
| `build_data.py` | Downloads the source maps and builds `data/atlas.npz` |
| `twin.py` | The matching engine (`Atlas.query(lat, lon, period)`) |
| `app.py` | Local web server and JSON API (standard library only) |
| `static/index.html` | The map page (Leaflet) |
| `evaluate.py` | Checks the core assumption on today's data |
| `make_demo_data.py` | Invented data for interface development only |

## How the match works

- Climate measures: average temperature, hottest-month high, coldest-month low, annual rainfall,
  rainfall seasonality, rain in the warmest quarter, rain in the coldest quarter
  (WorldClim BIO1, 5, 6, 12, 15, 18, 19).
- Rainfall amounts are square-rooted, then every measure is divided by its spread across all land,
  so each counts equally. The climate distance is the root-mean-square difference
  (0 = identical).
- Labels: distance up to 0.35 is a "close" match, up to 0.70 "partial", above that "poor".
  These cut-offs are our judgement, not a published standard.
- "Around 2040" is the average of the 2021-2040 and 2041-2060 projections. Projections are
  averaged across the climate models downloaded. Both averages are approximations.

## What we checked

- **Core assumption** (`evaluate.py`): for a random sample of farmed cells we find the best
  climate match at least 1,000 km away using today's climate for both, and measure the overlap
  in main crops (shared top-5 crops divided by all top-5 crops in either place). The baseline is
  a random farmed cell at least 1,000 km away.
  Result on real data (1,500 sampled farmed cells): main-crop overlap is 29% for climate
  matches against 15% for random farmed pairs (standard errors about 0.5 points). The
  closer-matching half scores 35%, the looser half 24%. Crop-mix cosine similarity is 0.44
  against 0.23. Caveat: SPAM places crops partly by climate-based suitability, so part of
  this link is built into the crop maps.
- **Identity test**: when the "future" is set equal to today's climate, the best match is the
  farm's own cell at distance 0.
- **Data build**: tested end to end on rasters written in the same file layout as the sources.
  On the real download it found 236,742 cells with crops.
- **Spot checks**: **TODO list two or three farms where the twin and crops look sensible, and one
  where the tool reports no good match.**

## Limits

- A twin matches temperature and rainfall only. Soil, irrigation, day length, pests, markets and
  local know-how also decide what grows. Crop lists are candidates to trial, not recommendations.
- Irrigated farms (for example Gezira) depend less on rainfall, so rainfall-based twins fit them
  less well. The app shows the irrigated share of cropland for the farm and each twin.
- "Today" is the 1970-2000 average, so some warming has already happened. Crop maps are for
  around 2010 and are themselves modelled estimates.
- One emissions pathway (SSP2-4.5 by default) and a small set of climate models.
- Harvested area shows what is grown, not how well it yields.

## Data sources

- WorldClim 2.1 baseline and CMIP6 projections, 10 arc-minutes: https://www.worldclim.org
  (Fick & Hijmans 2017). Check WorldClim's terms before redistributing; the `data/` folder is
  git-ignored for that reason and because of its size.
- SPAM 2010 v2.0 global harvested area, IFPRI: https://www.mapspam.info
  (Yu et al. 2020, doi:10.7910/DVN/PRFF8V).
- Map tiles and place names: OpenStreetMap and Nominatim.
