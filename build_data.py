#!/usr/bin/env python3
"""Download the public climate and crop maps and build data/atlas.npz.

Sources
  WorldClim 2.1 bioclimatic variables, 10 arc-minute grid
    - baseline climate ("today"): 1970-2000 average
    - CMIP6 projections: 2021-2040 and 2041-2060 averages, one file per climate model
  SPAM 2010 v2.0 global harvested area by crop, 5 arc-minute grid

Run:  python build_data.py            (about 400 MB of downloads, resumable)
      python build_data.py --models MPI-ESM1-2-HR   (smaller: one climate model)
"""
import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

logging.getLogger("tifffile").setLevel(logging.ERROR)   # hide harmless tag warnings

RES = 1 / 6            # 10 arc-minutes in degrees
H, W = 1080, 2160      # global 10 arc-minute grid
BIO = [1, 5, 6, 12, 15, 18, 19]   # bioclim variables kept (see twin.py for meanings)

BASE_URL = "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_bio.zip"
FUTURE_URLS = [
    "https://geodata.ucdavis.edu/cmip6/10m/{m}/{s}/wc2.1_10m_bioc_{m}_{s}_{p}.tif",
    "https://geodata.ucdavis.edu/climate/worldclim/2_1/cmip6/10m/{m}/{s}/wc2.1_10m_bioc_{m}_{s}_{p}.tif",
]
SPAM_NAME = "spam2010v2r0_global_harv_area.geotiff.zip"
SPAM_URL = "https://s3.amazonaws.com/mapspam/2010/v2.0/geotiff/" + SPAM_NAME   # often refuses downloads
SPAM_DOI = "doi:10.7910/DVN/PRFF8V"            # the dataset's home on Harvard Dataverse
DATAVERSE = "https://dataverse.harvard.edu"
SPAM_HELP = f"""
Could not download the SPAM crop maps automatically. Get the file by hand (about 144 MB):
  1. Open https://doi.org/10.7910/DVN/PRFF8V in a browser.
  2. Download {SPAM_NAME}
     (harvested area, GeoTIFF; not the CSV, physical area, yield or production files).
  3. Leave it in your Downloads folder, or move it to {{dest}}
  4. Run this script again. Everything already downloaded is kept.
"""
PERIODS = ["2021-2040", "2041-2060"]
DEFAULT_MODELS = ["MPI-ESM1-2-HR", "MIROC6", "UKESM1-0-LL"]


# ---------------------------------------------------------------- downloads
def download(url, dest):
    """Fetch url to dest. Returns True on success. Skips files already present."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have {dest.name}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {url}")
    ok = False
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-L", "--fail", "--retry", "3", "-C", "-",
                            "-o", str(part), url])
        ok = r.returncode == 0
    else:
        try:
            ctx = None
            try:
                import ssl, certifi
                ctx = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                pass
            req = urllib.request.Request(url, headers={"User-Agent": "climate-twin/1.0"})
            with urllib.request.urlopen(req, context=ctx) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            ok = True
        except Exception as e:           # noqa: BLE001
            print(f"  failed: {e}")
    if ok and part.exists() and part.stat().st_size > 0:
        part.rename(dest)
        return True
    part.unlink(missing_ok=True)
    return False


def fetch_text(url):
    """Return the body of a small text/JSON resource, or None."""
    try:
        if shutil.which("curl"):
            r = subprocess.run(["curl", "-sL", "--fail", "--max-time", "60", url],
                               capture_output=True, text=True)
            return r.stdout if r.returncode == 0 and r.stdout else None
        req = urllib.request.Request(url, headers={"User-Agent": "climate-twin/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()
    except Exception:                    # noqa: BLE001
        return None


def dataverse_spam_urls():
    """Ask Harvard Dataverse for the download address of the harvested-area GeoTIFF zip."""
    text = fetch_text(f"{DATAVERSE}/api/datasets/:persistentId/?persistentId={SPAM_DOI}")
    try:
        files = json.loads(text)["data"]["latestVersion"]["files"]
    except (TypeError, ValueError, KeyError):
        return []
    urls = []
    for f in files:
        label = str(f.get("label", "")).lower()
        if "harv" in label and "geotiff" in label and label.endswith(".zip"):
            urls.append(f"{DATAVERSE}/api/access/datafile/{f['dataFile']['id']}")
    return urls


def get_spam(raw):
    """Make sure raw/spam_harv_area.zip exists and is a real zip. Returns True on success."""
    dest = Path(raw) / "spam_harv_area.zip"

    def good():
        if dest.exists() and zipfile.is_zipfile(dest):
            return True
        dest.unlink(missing_ok=True)     # e.g. an error page saved under the zip's name
        return False

    if good():
        print(f"  have {dest.name}")
        return True
    # a copy the user already downloaded by hand
    for manual in (Path(raw) / SPAM_NAME, Path(SPAM_NAME), Path.home() / "Downloads" / SPAM_NAME):
        if manual.exists() and zipfile.is_zipfile(manual):
            print(f"  using {manual}")
            shutil.copyfile(manual, dest)
            return True
    if download(SPAM_URL, dest) and good():
        return True
    print("  first address failed; trying Harvard Dataverse")
    for url in dataverse_spam_urls():
        if download(url, dest) and good():
            return True
    print(SPAM_HELP.format(dest=dest))
    return False


# ------------------------------------------------------------ raster reading
def read_raster(path):
    """Return (bands[B,h,w] float32, pixel_scale, tiepoint, nodata) for a GeoTIFF."""
    try:
        import tifffile
        with tifffile.TiffFile(path) as tf:
            tags = tf.pages[0].tags
            scale = tags["ModelPixelScaleTag"].value if "ModelPixelScaleTag" in tags else None
            tie = tags["ModelTiepointTag"].value if "ModelTiepointTag" in tags else None
            nodata = None
            if "GDAL_NODATA" in tags:
                try:
                    nodata = float(str(tags["GDAL_NODATA"].value).strip().strip("\x00"))
                except ValueError:
                    nodata = None
            arr = tf.asarray()
    except Exception as first:           # noqa: BLE001
        try:
            import rasterio
        except ImportError:
            raise RuntimeError(
                f"Could not read {path}: {first}\n"
                "If this mentions compression, run:  pip install imagecodecs") from first
        with rasterio.open(path) as src:
            arr = src.read()
            t = src.transform
            scale, tie, nodata = (t.a, -t.e, 0), (0, 0, 0, t.c, t.f, 0), src.nodata
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = arr[None]
    elif arr.ndim == 3 and arr.shape[2] < arr.shape[0] and arr.shape[2] < arr.shape[1]:
        arr = np.moveaxis(arr, 2, 0)     # (h, w, bands) -> (bands, h, w)
    return arr, scale, tie, nodata


def clean(band, nodata):
    out = band.astype(np.float32, copy=True)
    bad = ~np.isfinite(out) | (out < -1e30)
    if nodata is not None and np.isfinite(nodata):
        bad |= out == np.float32(nodata)
    out[bad] = np.nan
    return out


def to_global(band, scale, tie, res, h, w):
    """Place a raster on the global grid of the given resolution."""
    if scale is None or tie is None:
        if band.shape == (h, w):
            return band
        raise ValueError(f"raster has shape {band.shape} and no georeferencing")
    if abs(scale[0] - res) > res * 0.01:
        raise ValueError(f"unexpected resolution {scale[0]} (wanted {res})")
    col0 = int(round((tie[3] + 180) / res))
    row0 = int(round((90 - tie[4]) / res))
    out = np.full((h, w), np.nan, np.float32)
    bh, bw = band.shape
    r0, c0, r1, c1 = max(row0, 0), max(col0, 0), min(row0 + bh, h), min(col0 + bw, w)
    out[r0:r1, c0:c1] = band[r0 - row0:r1 - row0, c0 - col0:c1 - col0]
    return out


def unzip(zip_path, out_dir):
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.rglob("*.tif")):
        return
    print(f"  unzipping {Path(zip_path).name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out_dir)


# -------------------------------------------------------------------- build
def load_baseline(raw):
    unzip(raw / "wc2.1_10m_bio.zip", raw / "base")
    layers = []
    for n in BIO:
        hits = list((raw / "base").rglob(f"*bio_{n}.tif"))
        if not hits:
            sys.exit(f"baseline file for bio_{n} not found under {raw/'base'}")
        arr, scale, tie, nodata = read_raster(hits[0])
        layers.append(to_global(clean(arr[0], nodata), scale, tie, RES, H, W))
    return np.stack(layers, -1)          # (H, W, 7) very cool thing


def load_future(raw, models, ssp, period):
    total, used = None, []
    for m in models:
        path = raw / f"wc2.1_10m_bioc_{m}_{ssp}_{period}.tif"
        if not path.exists():
            continue
        try:
            arr, scale, tie, nodata = read_raster(path)
            if arr.shape[0] != 19:
                raise ValueError(f"expected 19 bands, found {arr.shape[0]}")
            layers = [to_global(clean(arr[n - 1], nodata), scale, tie, RES, H, W) for n in BIO]
        except Exception as e:           # noqa: BLE001
            print(f"  skipping {path.name}: {e}")
            continue
        stack = np.stack(layers, -1)
        total = stack if total is None else total + stack
        used.append(m)
    if not used:
        sys.exit(f"no usable projection files for {period}")
    return total / len(used), used


def load_spam(raw):
    unzip(raw / "spam_harv_area.zip", raw / "spam")
    pat = re.compile(r"_H_([A-Za-z]{4})_([A-Za-z])\.tif$")
    files = {}
    for p in (raw / "spam").rglob("*.tif"):
        m = pat.search(p.name)
        if m:
            files[(m.group(1).lower(), m.group(2).upper())] = p
    codes = sorted({c for c, t in files if t == "A"})
    if not codes:
        sys.exit("no SPAM harvested-area rasters found (expected names like *_H_WHEA_A.tif)")
    area = np.zeros((len(codes), H, W), np.float32)
    irr = np.zeros((H, W), np.float32)

    def coarse(path):
        arr, scale, tie, nodata = read_raster(path)
        g = to_global(clean(arr[0], nodata), scale, tie, RES / 2, 2 * H, 2 * W)
        g = np.where(np.isfinite(g) & (g > 0), g, 0).astype(np.float32)
        return g.reshape(H, 2, W, 2).sum(axis=(1, 3))     # 5' -> 10', hectares add up

    for k, c in enumerate(codes):
        print(f"  crop {k + 1}/{len(codes)}: {c}", end="\r")
        area[k] = coarse(files[(c, "A")])
        if (c, "I") in files:
            irr += coarse(files[(c, "I")])
    print()
    return codes, area, irr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", default="data/raw", help="folder for downloaded files")
    ap.add_argument("--out", default="data/atlas.npz")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--ssp", default="ssp245", help="emissions pathway (ssp126/245/370/585)")
    ap.add_argument("--skip-download", action="store_true")
    a = ap.parse_args()
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)

    if not a.skip_download:
        print("1/4 downloading")
        if not download(BASE_URL, raw / "wc2.1_10m_bio.zip"):
            sys.exit("could not download the baseline climate")
        for p in PERIODS:
            for m in a.models:
                dest = raw / f"wc2.1_10m_bioc_{m}_{a.ssp}_{p}.tif"
                if not any(download(u.format(m=m, s=a.ssp, p=p), dest) for u in FUTURE_URLS):
                    print(f"  WARNING: no projection for {m} {p}; continuing without it")
        if not get_spam(raw):
            sys.exit(1)

    print("2/4 reading baseline climate")
    cur = load_baseline(raw)
    print("3/4 reading projections")
    fut, used = {}, {}
    for p in PERIODS:
        fut[p], used[p] = load_future(raw, a.models, a.ssp, p)
        print(f"  {p}: {', '.join(used[p])}")

    lat_ok = (90 - (np.arange(H) + 0.5) * RES > -60)[:, None]
    land = np.isfinite(cur).all(-1) & lat_ok
    for p in PERIODS:
        land &= np.isfinite(fut[p]).all(-1)
    rows, cols = np.nonzero(land)
    print(f"  {len(rows):,} land cells")

    print("4/4 reading crop maps")
    codes, area, irr = load_spam(raw)
    cell_area = area[:, rows, cols].T                   # (N, C)
    has = cell_area.sum(1) > 0
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        rows=rows.astype(np.int16), cols=cols.astype(np.int16),
        vars=np.array([f"bio{n}" for n in BIO]),
        cur=cur[rows, cols].astype(np.float32),
        periods=np.array(PERIODS),
        **{f"fut_{p}": fut[p][rows, cols].astype(np.float32) for p in PERIODS},
        models=np.array(sorted(set(sum(used.values(), [])))), ssp=np.array(a.ssp),
        crop_cells=np.nonzero(has)[0].astype(np.int32),
        crop_area=cell_area[has].astype(np.float32),
        crop_irr=irr[rows, cols][has].astype(np.float32),
        crop_codes=np.array(codes),
        synthetic=np.array(False),
    )
    print(f"wrote {out} ({out.stat().st_size / 1e6:.0f} MB), {int(has.sum()):,} cells with crops")


if __name__ == "__main__":
    main()
