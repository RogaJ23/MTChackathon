# Climate Twin Crop Advisor

**See your farm's future climate in places already farming under similar conditions today.**

*DNAForge × MTC Berkeley Hackathon 2026 · Agricultural Resilience*  
[GitHub repository](https://github.com/RogaJ23/MTChackathon) · Team ID: **[T4]**

## The problem

Climate forecasts tell farmers **what may change**, but not **what they could try**. For smallholder farmers and under-resourced communities, turning complex climate data into practical adaptation research can be especially difficult.

## Our solution

**Climate Twin** lets you choose a farm and explore how its climate could change around **2030, 2040, or 2050**, using published projections covering **2021–2060**. It searches **every farmed area on Earth** (about 237,000 grid cells of roughly 18 km) for places experiencing a similar climate **today** and shows what farmers grow there—giving local growers **ideas for small trials**, not guaranteed planting recommendations.

**Why it matters:** Agricultural extension officers can turn complex projections into a map, a printable handout, or a short message farmers can discuss and act on with local guidance.

## What it does

- **Choose a farm:** Click the interactive world map, search for a place, or enter coordinates.
- **Select a climate forecast:** Switch between **around 2030** (2021–2040 average), **around 2040** (2021–2060 average), and **around 2050** (2041–2060 average).
- **See what changes:** Compare today's climate with the selected future period, including projected temperature and rainfall changes and a detailed seven-variable climate table.
- **Find climate twins:** See up to five regions where farmers already experience similar conditions, with map locations and match-quality ratings.
- **Explore crop options:** Compare crops grown near your farm with those in its climate twins. Results group crops into **Candidates to trial**, **Likely still suited**, and **Worth watching**, with irrigation context. Weak matches do not generate crop advice.
- **Share the findings:** **Print farm report** makes a one-page handout with crop lists, seed-source regions, twin and climate tables, and caveats. **Copy text message** creates a short summary for SMS or WhatsApp.

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

**Quick demo:** Choose the Central Valley preset → select **around 2050** → view the projected climate shift and matching regions → compare crop lists → print a report or copy a message.

## Experimental: gene bank lookup

The seed card can also list gene bank samples (accessions) of each suggested crop collected near the top twin region, from the [Genesys PGR](https://www.genesys-pgr.org) catalogue. This is **built but off by default, and not yet tested against the live Genesys service**. It needs credentials issued by Genesys:

```bash
export GENESYS_CLIENT_ID="your-client-id"
export GENESYS_CLIENT_SECRET="your-client-secret"
.venv/bin/python app.py
```

Without credentials the app is unchanged. Never commit these values.

## What we tested

The repository's saved [evaluation results](data/validation.json) compare climate twins with random distant farmed regions across **1,500 locations**, using real (non-synthetic) atlas data.

| Crop similarity measure | Climate twins | Random regions |
|---|---:|---:|
| Main-crop overlap (shared top-5 crops ÷ all top-5 crops in either place) | **29.2%** | 15.4% |
| Crop-mix cosine similarity | **0.435** | 0.231 |

Climate twins share nearly **twice** the main crops of random pairs, and the gap is far larger than the sampling error (about 0.5 percentage points on each figure). Closer climate matches share more: **34.7%** for the closer-matching half against **23.7%** for the looser half.

These results support the **climate–crop similarity concept**, not future crop performance. One caveat: SPAM places crops partly by climate-based suitability, so part of this link is built into the crop maps.

We also checked that when the "future" is set equal to today's climate, the best match is the farm's own location at distance zero, and the team launched the app from a fresh GitHub clone. Farm-by-farm plausibility checks are not yet documented.

To reproduce the saved comparison:

```bash
.venv/bin/python evaluate.py --data data/atlas.npz --n 1500 --min-km 1000 --seed 0
```

## Challenges we faced

- **Why we used published climate projections:** A physical climate model simulates complex atmospheric and ocean processes and takes major scientific resources to develop. Even a credible ML emulator needs extensive historical data and compute. For a one-day hackathon, using established **WorldClim/CMIP6 projections** was more reliable than training a rushed climate model.
- **Poor hackathon Wi-Fi:** Downloading global climate and crop datasets was difficult under the time limit. We prioritized a **compact, prebuilt atlas** and an app judges could run locally.

## Data, limitations, and rebuilding

- **Climate:** [WorldClim 2.1](https://www.worldclim.org/) historical averages (1970–2000) and CMIP6 projections (default **SSP2-4.5**), averaged over three climate models: MPI-ESM1-2-HR, MIROC6 and UKESM1-0-LL. Seven temperature and rainfall measures are matched.
- **Crops:** [IFPRI SPAM 2010](https://doi.org/10.7910/DVN/PRFF8V) modeled harvested-area maps—not yields.
- **Maps:** MapLibre GL with OpenFreeMap/OpenStreetMap-based services.

**Important:** "Today" means the 1970–2000 average, and the crop maps are from around 2010. Match-quality labels (close, partial, poor) use cut-offs we chose. Climate twins do **not** account for soil, pests, water access, seed availability, costs, or local farming practices. Crop suggestions are hypotheses for **locally supervised trials**, not yield predictions or instructions to replace crops.

To rebuild the atlas from source data:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_data.py     # three climate models, about 400 MB; add --models MPI-ESM1-2-HR for a smaller one-model build
```

If the crop-map download fails, download **`spam2010v2r0_global_harv_area.geotiff.zip`** from [Harvard Dataverse](https://doi.org/10.7910/DVN/PRFF8V), place it in `~/Downloads`, and rerun the builder. Check source-data redistribution terms before publishing derived datasets.
