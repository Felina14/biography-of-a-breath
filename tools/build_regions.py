"""Rasterise Natural Earth (public domain) marine areas + physical regions to a 0.25-degree
grid of name ids -> ref/regions.npz (used by the API to say 'over the North Sea')."""
import json, sys, urllib.request, numpy as np
from matplotlib.path import Path
BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
KEEP = {"Desert", "Range/mtn", "Plateau", "Delta", "Basin", "Plain", "Peninsula", "Tundra", "Lowland", "Valley", "Gorge"}
lat = 90 - 0.125 - 0.25 * np.arange(720); lon = -180 + 0.125 + 0.25 * np.arange(1440)
LO, LA = np.meshgrid(lon, lat); pts = np.c_[LO.ravel(), LA.ravel()]
grid = np.zeros(LA.shape, np.int16); names = [""]
def polys(g):
    if g["type"] == "Polygon": return [g["coordinates"]]
    if g["type"] == "MultiPolygon": return g["coordinates"]
    return []
def paint(fn, keep=None, scalerank_max=9):
    fc = json.load(urllib.request.urlopen(BASE + fn, timeout=120))
    gp = lambda p, k: p.get(k) if p.get(k) is not None else p.get(k.upper())
    feats = sorted(fc["features"], key=lambda f: -(gp(f["properties"], "scalerank") or 0))  # big features first, small ones paint over
    n = 0
    for f in feats:
        p = f["properties"]; nm = gp(p, "name")
        if not nm or (keep and gp(p, "featurecla") not in keep) or (gp(p, "scalerank") or 0) > scalerank_max: continue
        names.append(nm); k = len(names) - 1
        for poly in polys(f["geometry"]):
            ring = np.array(poly[0]); x0, y0 = ring.min(0); x1, y1 = ring.max(0)
            m = (pts[:, 0] >= x0) & (pts[:, 0] <= x1) & (pts[:, 1] >= y0) & (pts[:, 1] <= y1)
            if not m.any(): continue
            inside = Path(ring).contains_points(pts[m])
            g = grid.ravel(); sel = np.nonzero(m)[0][inside]; g[sel] = k
        n += 1
    print(fn, n, "features")
paint("ne_10m_geography_marine_polys.geojson")
n_marine = len(names)
paint("ne_10m_geography_regions_polys.geojson", keep=KEEP, scalerank_max=6)
np.savez_compressed(sys.argv[1] if len(sys.argv) > 1 else "ref/regions.npz", grid=grid, names=np.array([n.title() if n.isupper() else n for n in names]), n_marine=np.array(n_marine))
print("named cells:", int((grid > 0).sum()), "names:", len(names))
