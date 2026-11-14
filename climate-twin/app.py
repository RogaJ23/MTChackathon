#!/usr/bin/env python3
"""Local web app.  Run:  python app.py   then open http://localhost:8000"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from twin import PERIOD_LABELS, VAR_INFO, Atlas

HERE = Path(__file__).parent
PRESETS = [
    ["Gezira, Sudan", 14.4, 33.5], ["Nakuru, Kenya", -0.3, 36.1],
    ["Punjab, India", 30.9, 75.85], ["Kansas, USA", 38.5, -98.5],
    ["Beauce, France", 48.2, 1.6], ["Central Valley, California", 36.7, -119.8],
    ["Mato Grosso, Brazil", -13.0, -56.0], ["North China Plain", 36.5, 115.5],
]


def make_handler(atlas, validation):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    self.send(200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/meta":
                    self.send(200, {
                        "periods": [[p, PERIOD_LABELS[p]] for p in atlas.periods],
                        "default_period": "mid" if "mid" in atlas.periods else atlas.periods[0],
                        "vars": [[v, *VAR_INFO.get(v, (v, "", 1))] for v in atlas.vars],
                        "models": atlas.models, "ssp": atlas.ssp, "synthetic": atlas.synthetic,
                        "presets": PRESETS, "validation": validation,
                    })
                elif url.path == "/api/twin":
                    res = atlas.query(float(q["lat"]), float(q["lon"]),
                                      period=q.get("period", "mid"),
                                      min_km=float(q.get("min_km", 100)))
                    self.send(200, res)
                else:
                    self.send(404, {"error": "not found"})
            except (KeyError, ValueError) as e:
                self.send(400, {"error": str(e)})
            except Exception as e:           # noqa: BLE001
                self.send(500, {"error": f"{type(e).__name__}: {e}"})
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/atlas.npz")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    print("loading atlas ...")
    atlas = Atlas(a.data)
    vpath = Path(a.data).with_name("validation.json")
    validation = json.loads(vpath.read_text()) if vpath.exists() else None
    if validation and bool(validation.get("synthetic")) != atlas.synthetic:
        validation = None                    # never show a check computed on different data
    print(f"{atlas.n:,} land cells, {int(atlas.farmed.sum()):,} farmed"
          + ("  [SYNTHETIC TEST DATA]" if atlas.synthetic else ""))
    print(f"open http://localhost:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(atlas, validation)).serve_forever()


if __name__ == "__main__":
    main()
