"""Ingest Lambda (EventBridge, every 6 h): pull the last 72 h of NOAA GFS analyses from the
public AWS Open Data bucket via .idx byte ranges and write a compact cube to our S3 bucket.
No xarray/cfgrib: decodes GRIB2 messages directly with eccodes."""
import datetime as dt, io, os, urllib.request
import numpy as np, boto3, eccodes

BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"
BUCKET, KEY = os.environ["DATA_BUCKET"], os.environ.get("CUBE_KEY", "cube/latest.npz")
HOURS = int(os.environ.get("HOURS_BACK", "72"))
ANL = [("UGRD", "10 m above ground"), ("VGRD", "10 m above ground"), ("UGRD", "850 mb"), ("VGRD", "850 mb"),
       ("TMP", "2 m above ground"), ("RH", "2 m above ground"), ("LAND", "surface")]
FC6 = [("PRATE", "surface")]
NAMES = ["u10", "v10", "u850", "v850", "t2m", "rh2m", "land"]
# optional hazard fields (if a file lacks one, it's stored as NaN and simply not shown)
OPT_ANL = [("GUST", "surface"), ("CAPE", "surface"), ("VIS", "surface")]; OPT_NAMES = ["gust", "cape", "vis"]
OPT_FC6 = [("CSNOW", "surface")]

def url(c, f): return f"{BASE}/gfs.{c:%Y%m%d}/{c:%H}/atmos/gfs.t{c:%H}z.pgrb2.0p25.f{f:03d}"
def get(u, rng=None):
    r = urllib.request.Request(u, headers={"Range": f"bytes={rng}"} if rng else {})
    with urllib.request.urlopen(r, timeout=60) as x: return x.read()
def exists(u):
    try: urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=20); return True
    except Exception: return False

def latest():
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    c = now.replace(hour=now.hour - now.hour % 6)
    for _ in range(8):
        if exists(url(c, 6) + ".idx"): return c
        c -= dt.timedelta(hours=6)
    raise RuntimeError("no recent GFS cycle")

def fields(c, f, wanted, optional=()):
    rows = [l.split(":") for l in get(url(c, f) + ".idx").decode().strip().splitlines()]
    out = {}
    for i, r in enumerate(rows):
        k = (r[3], r[4])
        if (k in wanted or k in optional) and k not in out:
            end = int(rows[i + 1][1]) - 1 if i + 1 < len(rows) else ""
            msg = eccodes.codes_new_from_message(get(url(c, f), f"{r[1]}-{end}"))
            ni, nj = eccodes.codes_get(msg, "Ni"), eccodes.codes_get(msg, "Nj")
            out[k] = eccodes.codes_get_values(msg).reshape(nj, ni)[::2, ::2].astype(np.float32)  # 0.25 -> 0.5 deg
            eccodes.codes_release(msg)
    if set(wanted) - set(out): raise RuntimeError(f"missing {set(wanted) - set(out)} in {url(c, f)}")
    for k in optional:
        if k not in out: out[k] = np.full((361, 720), np.nan, np.float32); print("optional field missing", k, url(c, f))
    return out

def handler(event=None, context=None):
    last = latest()
    cycles = [last - dt.timedelta(hours=6 * k) for k in range(HOURS // 6, -1, -1)]
    st = {n: [] for n in NAMES + OPT_NAMES + ["prate", "snow"]}
    for c in cycles:
        a = fields(c, 0, ANL, OPT_ANL); p = fields(c, 6, FC6, OPT_FC6)
        for n, k in zip(NAMES + OPT_NAMES, ANL + OPT_ANL): st[n].append(a[k])
        st["prate"].append(p[FC6[0]]); st["snow"].append(p[OPT_FC6[0]])
    s3 = boto3.client("s3")
    buf = io.BytesIO()
    np.savez_compressed(buf, times=np.array([c.timestamp() for c in cycles]),
                        lat=np.arange(90, -90.01, -0.5), lon=np.arange(0, 360, 0.5),
                        **{n: np.stack(v) for n, v in st.items()})
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=buf.getvalue()); past_bytes = buf.tell()
    # forecast cube: the latest cycle's forecasts f000..f072 every 6 h (for "where will it go?")
    fc = {n: [] for n in NAMES + OPT_NAMES + ["prate", "snow"]}; steps = list(range(0, HOURS + 1, 6))
    for f in steps:
        a = fields(last, f, ANL, OPT_ANL) if f else {k: st[n][-1] for n, k in zip(NAMES + OPT_NAMES, ANL + OPT_ANL)}
        p = fields(last, min(f + 6, 384), FC6, OPT_FC6)      # rain / snow over the next 6 h
        for n, k in zip(NAMES + OPT_NAMES, ANL + OPT_ANL): fc[n].append(a[k])
        fc["prate"].append(p[FC6[0]]); fc["snow"].append(p[OPT_FC6[0]])
    buf = io.BytesIO()
    np.savez_compressed(buf, times=np.array([(last + dt.timedelta(hours=f)).timestamp() for f in steps]),
                        lat=np.arange(90, -90.01, -0.5), lon=np.arange(0, 360, 0.5), **{n: np.stack(v) for n, v in fc.items()})
    s3.put_object(Bucket=BUCKET, Key="cube/forecast.npz", Body=buf.getvalue())
    return {"latest_cycle": last.isoformat(), "cycles": len(cycles), "past_bytes": past_bytes, "forecast_steps": len(steps), "forecast_bytes": buf.tell()}
