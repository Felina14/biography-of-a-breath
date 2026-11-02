"""Gate step 2: backward RK4 trajectory through the GFS wind cube, sampling the
weather near the modelled path every hour, plus first-cut diary events.
Usage: python gate/02_trajectory.py NAME LAT LON [level: 10m|850]"""
import json, math, sys, datetime as dt
import numpy as np

R = 6371000.0
D = dict(np.load("data/gfs_cube.npz"))   # load once (NpzFile re-reads on every access)
T, LAT, LON = D["times"], D["lat"], D["lon"]          # lat 90..-90, lon 0..359.5
dlat, dlon = LAT[0] - LAT[1], LON[1] - LON[0]

def bilin(field, la, lo):
    lo %= 360.0
    i = (LAT[0] - la) / dlat; j = lo / dlon
    i0 = int(np.clip(np.floor(i), 0, len(LAT) - 2)); j0 = int(np.floor(j)) % len(LON)
    fi, fj = i - i0, j - math.floor(j); j1 = (j0 + 1) % len(LON)
    return ((1-fi)*(1-fj)*field[i0, j0] + (1-fi)*fj*field[i0, j1]
            + fi*(1-fj)*field[i0+1, j0] + fi*fj*field[i0+1, j1])

def at_time(stack, t, la, lo):
    k = int(np.clip(np.searchsorted(T, t) - 1, 0, len(T) - 2))
    w = (t - T[k]) / (T[k+1] - T[k])
    return (1-w) * bilin(stack[k], la, lo) + w * bilin(stack[k+1], la, lo)

def prate_at(t, la, lo):   # 6-h average from the cycle that starts the interval
    k = int(np.clip(np.searchsorted(T, t, side="right") - 1, 0, len(T) - 1))
    return bilin(D["prate"][k], la, lo) * 3600.0          # mm/h

def wind(t, la, lo, lev):
    return at_time(D[f"u{lev}"], t, la, lo), at_time(D[f"v{lev}"], t, la, lo)

def step(t, la, lo, h, lev):
    def f(t, la, lo):
        u, v = wind(t, la, lo, lev)
        return (v / R) * 180/math.pi, (u / (R * math.cos(math.radians(la)))) * 180/math.pi
    k1 = f(t, la, lo)
    k2 = f(t + h/2, la + h/2*k1[0], lo + h/2*k1[1])
    k3 = f(t + h/2, la + h/2*k2[0], lo + h/2*k2[1])
    k4 = f(t + h, la + h*k3[0], lo + h*k3[1])
    return (la + h/6*(k1[0]+2*k2[0]+2*k3[0]+k4[0]),
            lo + h/6*(k1[1]+2*k2[1]+2*k3[1]+k4[1]))

def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dp = p2 - p1; dl = math.radians(b[1] - a[1])
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * 6371.0 * math.asin(math.sqrt(x))

def main():
    name, la, lo = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    lev = sys.argv[4] if len(sys.argv) > 4 else "10"
    lev = "10" if lev.startswith("10") else "850"
    t, h = T[-1], -900.0                                   # arrive at latest analysis; 15-min steps back
    pts, km = [], 0.0
    for n in range(int((T[-1] - T[0]) / 900) + 1):
        if n % 4 == 0:
            u, v = wind(t, la, lo, lev)
            pts.append(dict(hours_ago=round((T[-1]-t)/3600, 2), lat=round(la, 4), lon=round(((lo+180)%360)-180, 4),
                            km_travelled=round(km, 1), wind_kmh=round(math.hypot(u, v)*3.6, 1),
                            temp_c=round(at_time(D["t2m"], t, la, lo)-273.15, 1),
                            rh=round(at_time(D["rh2m"], t, la, lo), 0),
                            rain_mmh=round(prate_at(t, la, lo), 2),
                            land=bool(at_time(D["land"], t, la, lo) > 0.5)))
        if t + h < T[0] or abs(la) > 85: break
        nla, nlo = step(t, la, lo, h, lev)
        km += hav((la, lo), (nla, nlo)); la, lo, t = nla, nlo, t + h
    pts.reverse()                                          # chronological: oldest first
    total = max(p["km_travelled"] for p in pts)
    for p in pts:                                          # km_travelled was measured backwards from arrival
        p["km_to_arrival"] = p.pop("km_travelled"); p["km_from_start"] = round(total - p["km_to_arrival"], 1)
    ev, last_t = [], None
    for i, p in enumerate(pts):
        prev = pts[i-1] if i else None
        if i == 0: ev.append((p, "start", f"{p['hours_ago']:.0f} h ago over {'land' if p['land'] else 'sea'}, {p['temp_c']} C, {p['rh']:.0f}% humidity"))
        elif p["land"] != prev["land"]: ev.append((p, "coast", f"crossed from {'sea to land' if p['land'] else 'land to sea'}"))
        if p["rain_mmh"] >= 0.2 and (not prev or prev["rain_mmh"] < 0.2): ev.append((p, "rain", f"modelled rain near the path ({p['rain_mmh']} mm/h)"))
        if last_t is not None and abs(p["temp_c"] - last_t) >= 6: ev.append((p, "temp", f"temperature now {p['temp_c']} C")); last_t = p["temp_c"]
        if last_t is None: last_t = p["temp_c"]
    ev.append((pts[-1], "arrive", f"arrived after {total:.0f} km"))
    out = dict(name=name, level=f"{lev} m" if lev == "10" else "850 hPa",
               arrival_utc=dt.datetime.fromtimestamp(T[-1], dt.timezone.utc).isoformat(),
               total_km=round(total, 1), points=pts,
               events=[dict(hours_ago=p["hours_ago"], lat=p["lat"], lon=p["lon"], kind=k, text=s) for p, k, s in ev])
    fn = f"out/journey_{name}_{lev}.json"
    json.dump(out, open(fn, "w"), indent=1)
    print(f"{name} ({out['level']}): {len(pts)} hourly points, {total:.0f} km, {len(ev)} events -> {fn}")
    for e in out["events"]: print(f"  -{e['hours_ago']:>5.0f} h  ({e['lat']:.2f},{e['lon']:.2f})  {e['text']}")

if __name__ == "__main__": main()
