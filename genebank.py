"""Optional lookup of gene bank accessions collected in a twin region (Genesys PGR).

OFF unless the environment variables GENESYS_CLIENT_ID and GENESYS_CLIENT_SECRET are set
before app.py starts. Genesys issues those credentials; the client must be enabled for the
OAuth "client credentials" grant. Every failure is caught and reported, so the rest of the
app keeps working.

NOT TESTED against the live Genesys service. The request format follows the genesysr R client.
"""
import csv
import io
import json
import os
import time
import urllib.parse
import urllib.request

SERVER = os.environ.get("GENESYS_SERVER", "https://api.genesys-pgr.org")
QUERY_PATH = os.environ.get("GENESYS_QUERY_PATH", "/api/v1/acn/query")

GENUS = {
    "Wheat": "Triticum", "Rice": "Oryza", "Maize": "Zea", "Barley": "Hordeum", "Sorghum": "Sorghum",
    "Pearl millet": "Pennisetum", "Small millet": "Eleusine", "Millet": "Pennisetum",
    "Potato": "Solanum", "Sweet potato": "Ipomoea", "Yams": "Dioscorea", "Cassava": "Manihot",
    "Beans": "Phaseolus", "Chickpea": "Cicer", "Cowpea": "Vigna", "Pigeon pea": "Cajanus",
    "Lentil": "Lens", "Soybean": "Glycine", "Groundnut": "Arachis", "Coconut": "Cocos",
    "Oil palm": "Elaeis", "Sunflower": "Helianthus", "Rapeseed": "Brassica", "Sesame": "Sesamum",
    "Sugarcane": "Saccharum", "Sugar beet": "Beta", "Cotton": "Gossypium", "Arabica coffee": "Coffea",
    "Robusta coffee": "Coffea", "Coffee": "Coffea", "Cocoa": "Theobroma", "Tea": "Camellia",
    "Tobacco": "Nicotiana", "Banana": "Musa", "Plantain": "Musa",
}


def _ssl_context():
    try:
        import ssl, certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def _pick(row, *names):
    low = {str(k).lower().replace("_", "").replace(".", ""): v for k, v in row.items()}
    for n in names:
        v = low.get(n.lower())
        if v not in (None, "", "NA"):
            return str(v)
    return ""


class Genebank:
    def __init__(self):
        self.client_id = os.environ.get("GENESYS_CLIENT_ID", "")
        self.secret = os.environ.get("GENESYS_CLIENT_SECRET", "")
        self._token, self._expires = None, 0.0

    @property
    def enabled(self):
        return bool(self.client_id and self.secret)

    def _open(self, req):
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as r:
            return r.read().decode("utf-8", "replace")

    def token(self):
        if self._token and time.time() < self._expires - 30:
            return self._token
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "openid",
                                       "client_id": self.client_id, "client_secret": self.secret}).encode()
        req = urllib.request.Request(SERVER + "/oauth/token", data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded",
                                              "Accept": "application/json", "User-Agent": "climate-twin/1.0"})
        tok = json.loads(self._open(req))
        self._token = tok["access_token"]
        self._expires = time.time() + float(tok.get("expires_in", 300))
        return self._token

    def accessions(self, crop, lat, lon, box=3.0, limit=8):
        """Accessions of the crop's genus collected within +/- box degrees of (lat, lon)."""
        if not self.enabled:
            return {"enabled": False}
        genus = GENUS.get(crop)
        if not genus:
            return {"enabled": True, "genus": None, "items": [], "note": "No genus mapping for this crop."}
        try:
            filters = {"taxonomy": {"genus": [genus]},
                       "geo": {"latitude": {"ge": round(lat - box, 3), "le": round(lat + box, 3)},
                               "longitude": {"ge": round(lon - box, 3), "le": round(lon + box, 3)}}}
            url = f"{SERVER}{QUERY_PATH}?p=0&l={int(limit)}"
            req = urllib.request.Request(url, data=json.dumps(filters).encode(), method="POST", headers={
                "Authorization": "Bearer " + self.token(), "Accept": "text/csv",
                "Content-Type": "application/json", "User-Agent": "climate-twin/1.0"})
            text = self._open(req)
            return {"enabled": True, "genus": genus, "items": self._parse(text)[:limit]}
        except Exception as e:           # noqa: BLE001  any failure must not break the app
            return {"enabled": True, "genus": genus, "items": [], "error": f"{type(e).__name__}: {e}"[:200]}

    @staticmethod
    def _parse(text):
        text = text.lstrip("﻿").strip()
        if not text:
            return []
        if text[0] in "{[":
            data = json.loads(text)
            rows = data.get("content", []) if isinstance(data, dict) else data
            flat = []
            for r in rows:
                t = r.get("taxonomy") or {}
                inst = r.get("institute") or {}
                flat.append({"accessionnumber": r.get("accessionNumber"), "accessionname": r.get("accessionName"),
                             "institutecode": r.get("instituteCode") or inst.get("code"), "doi": r.get("doi"),
                             "taxon": t.get("taxonName") or " ".join(x for x in (t.get("genus"), t.get("species")) if x)})
            rows = flat
        else:
            dialect = "excel-tab" if "\t" in text.splitlines()[0] else "excel"
            rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
        out = []
        for r in rows:
            number = _pick(r, "accessionNumber", "ACCENUMB", "acceNumb")
            if not number:
                continue
            taxon = _pick(r, "taxon", "taxonomytaxonName", "taxonName") or " ".join(
                x for x in (_pick(r, "taxonomygenus", "GENUS"), _pick(r, "taxonomyspecies", "SPECIES")) if x)
            doi = _pick(r, "DOI")
            out.append({"number": number, "name": _pick(r, "accessionName", "ACCENAME"),
                        "institute": _pick(r, "instituteCode", "INSTCODE", "institutecode"),
                        "taxon": taxon, "url": ("https://doi.org/" + doi) if doi else ""})
        return out
