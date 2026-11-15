# Climate Twin Crop Advisor

**See your farm's future climate in places already farming under similar conditions today.**

*DNAForge × MTC Berkeley Hackathon 2026 · Agricultural Resilience*  
[GitHub repository](https://github.com/RogaJ23/MTChackathon) · Team ID: **[T4]**

## The problem

Climate forecasts tell farmers **what may change**, but not **what they could try**. For smallholder farmers and under-resourced communities, turning complex climate data into practical adaptation research can be especially difficult.

## Our solution

**Climate Twin** lets you select a farm, explore its projected future climate, and find farmed regions experiencing similar conditions **today**. It then shows which crops are grown in those regions as **ideas for small local trials**—not guaranteed planting recommendations.

**Why it matters:** Agricultural extension officers can turn complex projections into a map, a printable handout, or a short message farmers can discuss and act on with local guidance.

## What it does

- **Explore future climate:** Compare seven temperature and rainfall indicators for your farm across historical and future periods.
- **Find climate twins:** Map up to five farmed regions with climates resembling your farm's projected conditions.
- **Compare crops:** See **Candidates to trial**, **Likely still suited**, and **Worth watching**, alongside irrigation context.
- **Show uncertainty:** Label matches *close*, *partial*, or *poor*. Avoid crop suggestions when no suitable farmed match is found.
- **Print farm report:** Create a one-page handout with crop lists, twin regions to ask about seed, climate and twin tables, and caveats.
- **Copy text message:** Share a plain-language climate and crop summary through SMS or WhatsApp.

## Try it locally

The repository includes a prebuilt climate-and-crop atlas, so **you do not need to download the large source datasets** just to run the app.

```bash
git clone https://github.com/RogaJ23/MTChackathon.git
cd MTChackathon
python3 -m venv .venv
.venv/bin/python -m pip install numpy
.venv/bin/python app.py
```

Open **http://localhost:8000**. Internet access is needed for map tiles and place search; no API key is required.

**Quick demo:** Choose a farm preset → select a future period → inspect its best climate twin → compare crops → print a report or copy a message.

## What we tested

The repository's saved [evaluation results](data/validation.json) compare climate twins with random distant farmed regions across **1,500 locations**, using real (non-synthetic) atlas data.

| Crop similarity measure | Climate twins | Random regions |
|---|---:|---:|
| Shared top-five crops | **29.2%** | 15.4% |
| Crop-mix cosine similarity | **0.435** | 0.231 |

These results support the **climate–crop similarity concept**, not future crop performance. The team also successfully launched the app from a fresh GitHub clone. **Six to eight farm-specific plausibility checks remain to be documented**, including any poor or missing matches.

To reproduce the saved comparison:

```bash
.venv/bin/python evaluate.py --data data/atlas.npz --n 1500 --min-km 1000 --seed 0
```

## Challenges we faced

- **Why we used published climate projections:** A physical climate model simulates complex atmospheric and ocean processes and takes major scientific resources to develop. Even a credible ML emulator needs extensive historical data and compute. For a one-day hackathon, using established **WorldClim/CMIP6 projections** was more reliable than training a rushed climate model.
- **Poor hackathon Wi-Fi:** Downloading global climate and crop datasets was difficult under the time limit. We prioritized a **compact, prebuilt atlas** and an app judges could run locally.

## Data, limitations, and rebuilding

- **Climate:** [WorldClim 2.1](https://www.worldclim.org/) historical averages (1970–2000) and CMIP6 projections (default **SSP2-4.5**).
- **Crops:** [IFPRI SPAM 2010](https://doi.org/10.7910/DVN/PRFF8V) modeled harvested-area maps—not yields.
- **Maps:** MapLibre GL with OpenFreeMap/OpenStreetMap-based services.

**Important:** Climate twins do **not** account for soil, pests, water access, seed availability, costs, or local farming practices. Crop suggestions are hypotheses for **locally supervised trials**, not yield predictions or instructions to replace crops.

To rebuild the atlas from source data:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_data.py --models MPI-ESM1-2-HR
```

If the crop-map download fails, download **`spam2010v2r0_global_harv_area.geotiff.zip`** from [Harvard Dataverse](https://doi.org/10.7910/DVN/PRFF8V), place it in `~/Downloads`, and rerun the builder. Check source-data redistribution terms before publishing derived datasets.
