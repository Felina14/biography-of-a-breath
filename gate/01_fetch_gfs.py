"""Gate step 1: fetch the last 72 h of NOAA GFS fields from the AWS Open Data bucket
(noaa-gfs-bdp-pds) using .idx byte ranges, so we download only the fields we need.
Writes data/gfs_cube.npz with 0.5-degree global arrays."""
import datetime as dt, io, sys, tempfile, os
import numpy as np, requests, xarray as xr

BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"
HOURS_BACK = int(os.environ.get("HOURS_BACK", "72"))
# (variable, level) taken from the analysis (f000) of each cycle
ANL = [("UGRD", "10 m above ground"), ("VGRD", "10 m above ground"),
       ("UGRD", "850 mb"), ("VGRD", "850 mb"),
       ("TMP", "2 m above ground"), ("RH", "2 m above ground"),
       ("LAND", "surface")]
# precipitation rate averaged over the next 6 h, from f006 of each cycle
FC6 = [("PRATE", "surface")]

def url(c, f): return f"{BASE}/gfs.{c:%Y%m%d}/{c:%H}/atmos/gfs.t{c:%H}z.pgrb2.0p25.f{f:03d}"

def latest_cycle():
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    c = now.replace(hour=now.hour - now.hour % 6)
    for _ in range(8):
        # need f006 of the latest cycle too (for the last precip interval)
        if requests.head(url(c, 6) + ".idx", timeout=20).status_code == 200:
            return c
        c -= dt.timedelta(hours=6)
    sys.exit("No recent GFS cycle found")

def fetch(c, f, wanted):
    idx = requests.get(url(c, f) + ".idx", timeout=30).text.strip().splitlines()
    rows = [l.split(":") for l in idx]
    out = {}
    for i, r in enumerate(rows):
        key = (r[3], r[4])
        if key in wanted and key not in out:
            start = int(r[1]); end = int(rows[i + 1][1]) - 1 if i + 1 < len(rows) else ""
            b = requests.get(url(c, f), headers={"Range": f"bytes={start}-{end}"}, timeout=60).content
            with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as t:
                t.write(b); p = t.name
            ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""})
            v = list(ds.data_vars)[0]
            out[key] = ds[v].values[::2, ::2].astype(np.float32)   # 0.25 -> 0.5 degree
            lat, lon = ds.latitude.values[::2], ds.longitude.values[::2]
            ds.close(); os.remove(p)
    missing = set(wanted) - set(out)
    if missing: sys.exit(f"Missing {missing} in {url(c, f)}")
    return out, lat, lon

def main():
    last = latest_cycle()
    cycles = [last - dt.timedelta(hours=6 * k) for k in range(HOURS_BACK // 6, -1, -1)]
    print("Latest cycle:", last, "| cycles:", len(cycles))
    stacks = {k: [] for k in ANL + FC6}
    for c in cycles:
        a, lat, lon = fetch(c, 0, ANL)
        p, _, _ = fetch(c, 6, FC6)
        for k in ANL: stacks[k].append(a[k])
        for k in FC6: stacks[k].append(p[k])
        print("  ok", c)
    np.savez_compressed("data/gfs_cube.npz",
        times=np.array([c.timestamp() for c in cycles]), lat=lat, lon=lon,
        u10=np.stack(stacks[ANL[0]]), v10=np.stack(stacks[ANL[1]]),
        u850=np.stack(stacks[ANL[2]]), v850=np.stack(stacks[ANL[3]]),
        t2m=np.stack(stacks[ANL[4]]), rh2m=np.stack(stacks[ANL[5]]),
        land=np.stack(stacks[ANL[6]]), prate=np.stack(stacks[FC6[0]]))
    print("Saved data/gfs_cube.npz", os.path.getsize("data/gfs_cube.npz") // 1024, "KB")

if __name__ == "__main__": main()
