"""Journey API (Lambda Function URL). GET ?lat=..&lon=..[&level=850|10]
Rewinds the air arriving at any point on Earth through the latest NOAA GFS winds (72 h),
samples the weather near the path, names the seas/regions/towns it crossed, and rewinds
24 companion parcels around the release point. Everything computed live per request."""
import io, json, math, os, time
import numpy as np, boto3

S3 = boto3.client("s3"); BUCKET = os.environ["DATA_BUCKET"]
COUNTRY = json.load(open(os.path.join(os.path.dirname(__file__), "countries.json"), encoding="utf-8"))
R = 6371000.0; _C = {}

def load(key):
    if key not in _C:
        _C[key] = dict(np.load(io.BytesIO(S3.get_object(Bucket=BUCKET, Key=key)["Body"].read()), allow_pickle=False))
    return _C[key]

def cube(key="cube/latest.npz"):
    # refresh an in-memory cube if a newer one was ingested (checked at most every 10 min)
    now = time.time(); ck = "cube::" + key
    if ck not in _C or now - _C.get(ck + "_t", 0) > 600:
        head = S3.head_object(Bucket=BUCKET, Key=key)
        if _C.get(ck + "_etag") != head["ETag"]:
            _C.pop(key, None); _C[ck] = load(key); _C[ck + "_etag"] = head["ETag"]
        _C[ck + "_t"] = now
    return _C[ck]

class Field:
    def __init__(s, D):
        s.D, s.T = D, D["times"]; s.nlat, s.nlon = len(D["lat"]), len(D["lon"])
    def bil(s, F, la, lo):                      # vectorised bilinear on a 0.5-degree global grid
        i = np.clip((90.0 - la) / 0.5, 0, s.nlat - 1.001); j = np.mod(lo, 360.0) / 0.5
        i0 = np.floor(i).astype(int); j0 = np.floor(j).astype(int) % s.nlon; j1 = (j0 + 1) % s.nlon
        fi, fj = i - i0, j - np.floor(j)
        return (1-fi)*(1-fj)*F[i0, j0] + (1-fi)*fj*F[i0, j1] + fi*(1-fj)*F[i0+1, j0] + fi*fj*F[i0+1, j1]
    def at(s, name, t, la, lo):
        T = s.T; k = int(np.clip(np.searchsorted(T, t) - 1, 0, len(T) - 2)); w = (t - T[k]) / (T[k+1] - T[k])
        S = s.D[name]; return (1-w) * s.bil(S[k], la, lo) + w * s.bil(S[k+1], la, lo)
    def rain(s, t, la, lo):
        k = int(np.clip(np.searchsorted(s.T, t, side="right") - 1, 0, len(s.T) - 1))
        return s.bil(s.D["prate"][k], la, lo) * 3600.0

def rewind(F, la, lo, lev, forward=False):
    """RK4 for many parcels at once, backward (default) or forward in time. Returns hourly states, oldest first."""
    T = F.T; t, h = (T[0], 900.0) if forward else (T[-1], -900.0); la = la.astype(float).copy(); lo = lo.astype(float).copy()
    def f(t, a, b):
        u, v = F.at(f"u{lev}", t, a, b), F.at(f"v{lev}", t, a, b)
        return (v / R) * 180/math.pi, (u / (R * np.cos(np.radians(a)))) * 180/math.pi
    out = []
    for n in range(int((T[-1] - T[0]) / 900) + 1):
        if n % 4 == 0: out.append((t, la.copy(), lo.copy()))
        if (t + h > T[-1]) if forward else (t + h < T[0]): break
        k1 = f(t, la, lo); k2 = f(t+h/2, la+h/2*k1[0], lo+h/2*k1[1]); k3 = f(t+h/2, la+h/2*k2[0], lo+h/2*k2[1]); k4 = f(t+h, la+h*k3[0], lo+h*k3[1])
        la = np.clip(la + h/6*(k1[0]+2*k2[0]+2*k3[0]+k4[0]), -89, 89); lo = lo + h/6*(k1[1]+2*k2[1]+2*k3[1]+k4[1])
        t = t + h
    if not forward: out.reverse()
    return out

def hav(a1, o1, a2, o2):
    p1, p2 = np.radians(a1), np.radians(a2); dl = np.radians(o2 - o1)
    x = np.sin((p2-p1)/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(x, 0, 1)))

def region_name(la, lo):
    G = load("ref/regions.npz")                 # 0.25-degree raster of Natural Earth marine + physical region ids
    i = int(np.clip((90 - la) / 0.25, 0, G["grid"].shape[0] - 1)); j = int(np.mod(lo + 180, 360) / 0.25) % G["grid"].shape[1]
    k = int(G["grid"][i, j])
    if k <= 0: return (None, None)
    AB = {"Ra.": "Range", "Mts.": "Mountains", "Mt.": "Mount", "Pen.": "Peninsula", "Is.": "Islands", "I.": "Island", "Pl.": "Plain",
          "Plat.": "Plateau", "Des.": "Desert", "Str.": "Strait", "G.": "Gulf", "B.": "Bay", "C.": "Cape", "L.": "Lake", "Arch.": "Archipelago"}
    nm = " ".join(AB.get(w, w if w.lower() not in ("of", "the", "and", "de") or n == 0 else w.lower()) for n, w in enumerate(str(G["names"][k]).split()))
    return (nm, k < int(G["n_marine"]))

def downwind(path_la, path_lo, ahead, corridor=25.0):
    P = load("ref/places.npz"); la, lo, pop = P["lat"], P["lon"], P["pop"]
    m = (la > path_la.min()-.6) & (la < path_la.max()+.6) & (lo > path_lo.min()-.6) & (lo < path_lo.max()+.6); out = []
    import re as _re; SKIP = _re.compile(r'(metropolitan|stadtbezirk|bezirk|district|ward|zone|tehsil)', _re.I)
    for i in np.nonzero(m)[0]:
        if SKIP.search(str(P["name"][i])) or hav(la[i], lo[i], path_la[0], path_lo[0]) < 30: continue
        d = hav(la[i], lo[i], path_la, path_lo); j = int(np.argmin(d))
        if d[j] <= corridor: out.append(dict(name=clean_name(P["name"][i]), country=COUNTRY.get(str(P["country"][i]), str(P["country"][i])),
                                             population=int(pop[i]), reached_in_hours=round(float(ahead[j]), 1),
                                             lat=round(float(la[i]), 3), lon=round(float(lo[i]), 3), km_from_path=round(float(d[j]), 1)))
    out.sort(key=lambda x: x["reached_in_hours"]); return out

def places_near(path_la, path_lo, hours, corridor=25.0, max_stops=12):
    P = load("ref/places.npz")                  # Overture localities, pop >= 15k
    la, lo, pop = P["lat"], P["lon"], P["pop"]
    m = (la > path_la.min()-.6) & (la < path_la.max()+.6) & (lo > path_lo.min()-.6) & (lo < path_lo.max()+.6)
    import re as _re; SKIP = _re.compile(r'(metropolitan|stadtbezirk|bezirk|innenstadt|district|ward|zone|arrondissement|tehsil)', _re.I)
    idx = [i for i in np.nonzero(m)[0] if not SKIP.search(str(P['name'][i]))]; hits = []
    for i in idx:
        d = hav(la[i], lo[i], path_la, path_lo); j = int(np.argmin(d))
        if d[j] <= corridor: hits.append((int(pop[i]), i, j, float(d[j])))
    hits.sort(reverse=True); chosen = []
    for p, i, j, d in hits:
        if all(hav(la[i], lo[i], la[c[1]], lo[c[1]]) >= 60 for c in chosen): chosen.append((p, i, j, d))
        if len(chosen) >= max_stops: break
    stops = [dict(name=clean_name(P["name"][i]), region=str(P["region"][i]), country=str(P["country"][i]), country_name=COUNTRY.get(str(P["country"][i]), str(P["country"][i])), population=p,
                  lat=round(float(la[i]), 4), lon=round(float(lo[i]), 4), dist_km=round(d, 1), hour_index=j) for p, i, j, d in chosen]
    countries = sorted({str(P["country"][h[1]]) for h in hits})
    return stops, dict(countries=countries, towns_15k_plus=len(hits), people_in_towns=int(sum(h[0] for h in hits)))

def handler(event, context):
    if ((event or {}).get("rawPath") or "").rstrip("/").endswith("/narrate"):
        return narrate(event)
    q = (event or {}).get("queryStringParameters") or {}
    if q.get("wind"):                                # the planet's live wind for the landing globe (latest NOAA GFS analysis, ~1.5 km up, 3-degree grid)
        try:
            D = cube("cube/latest.npz"); k = len(D["times"]) - 1; st = 6
            u = D["u850"][k][::st, ::st]; v = D["v850"][k][::st, ::st]
            return resp(200, dict(lat0=float(D["lat"][0]), lon0=float(D["lon"][0]), step=float(abs(D["lat"][1] - D["lat"][0]) * st), nlat=int(u.shape[0]), nlon=int(u.shape[1]),
                                  time_utc=time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(float(D["times"][k]))),
                                  u=[round(float(x), 1) for x in np.nan_to_num(u).ravel()], v=[round(float(x), 1) for x in np.nan_to_num(v).ravel()]), cache=3600)
        except Exception as e: return resp(500, {"error": repr(e)[:200]})
    if q.get("here"):
        try: return resp(200, here_forecast(float(q["lat"]), float(q["lon"])), cache=600)
        except Exception as e: return resp(400, {"error": str(e)})
    return journey(event)

def place_names(lats, lons):
    """Amazon Location Service (Places v2 ReverseGeocode): the nearest named settlement to each point, even small villages
    our 15k+ town index leaves out. One call per point, in parallel; None where nothing is named nearby or the call fails."""
    from concurrent.futures import ThreadPoolExecutor
    try: geo = boto3.client("geo-places")
    except Exception as e: print(json.dumps({"geo": "client unavailable", "error": repr(e)[:160]})); return [None] * len(lats)
    def one(ll):
        la, lo = ll
        try:
            r = geo.reverse_geocode(QueryPosition=[((float(lo) + 180) % 360) - 180, float(la)], QueryRadius=60000, MaxResults=1,
                                    Filter={"IncludePlaceTypes": ["Locality"]}, Language="en")
            it = (r.get("ResultItems") or [None])[0]
            if not it: return None
            ad = it.get("Address") or {}
            loc = ad.get("Locality")
            district = ad.get("District") or (it.get("Title") or "").split(",")[0] if not loc else None
            area = ((ad.get("SubRegion") or {}).get("Name") or (ad.get("Region") or {}).get("Name"))
            if not (loc or district or area): return None
            return dict(name=loc or district or area, kind="settlement" if loc else "district", area=area,
                        country=(ad.get("Country") or {}).get("Name"), km=round((it.get("Distance") or 0) / 1000))
        except Exception as e:
            print(json.dumps({"geo": "reverse_geocode failed", "error": repr(e)[:160]})); return None
    with ThreadPoolExecutor(8) as ex: return list(ex.map(one, zip(lats, lons)))

def nearest_town_to_path(path_la, path_lo, hours_rel):
    """The closest town of 15,000+ people to any point of the path (any distance), and when the air is closest to it."""
    P = load("ref/places.npz"); best = None
    for i in range(0, len(path_la), 2):
        d = hav(P["lat"], P["lon"], path_la[i], path_lo[i]); j = int(np.argmin(d))
        if best is None or d[j] < best[0]: best = (float(d[j]), j, i)
    if best is None: return None
    d, j, i = best
    return dict(name=clean_name(P["name"][j]), country=COUNTRY.get(str(P["country"][j]), str(P["country"][j])), population=realpop(P["pop"][j]),
                km_from_path=round(d), at_hour=round(float(hours_rel[i])))

def label(p):
    if p.get("near") and p["near"]["km"] <= 25: return p["near"]["name"]
    if p.get("place") and p["place"]["km"] <= 30 and p["place"].get("kind") != "district": return p["place"]["name"]
    if p.get("region"): return ("the " + p["region"]) if p.get("marine") else p["region"]
    return f"{abs(p['lat']):.1f}°{'N' if p['lat'] >= 0 else 'S'}, {abs(p['lon']):.1f}°{'E' if p['lon'] >= 0 else 'W'}"

def discoveries(pts, tkey, here=None, nearest=None, stops=None):
    """Facts about THIS breath, computed from its own data - Puff's 'discoveries'. tkey(p) = signed hours (negative = past)."""
    out = []
    def when(h): h = round(h); return "right now" if h == 0 else (f"{-h} hours ago" if h < 0 else f"in {h} hours")
    run, best = [], []
    for p in pts:
        if p.get("near") is None: run.append(p)
        else:
            if len(run) > len(best): best = run
            run = []
    if len(run) > len(best): best = run
    if len(best) >= 12:
        km = abs(best[-1]["km_from_start"] - best[0]["km_from_start"])
        out.append(dict(kind="emptiness", text=f"For {len(best) - 1} hours and {round(km):,} km, no town of 15,000+ people lay within 60 km of me", hours=len(best) - 1, km=round(km)))
    if not stops and nearest:
        out.append(dict(kind="nearest_people", text=f"The nearest town of 15,000+ people was {nearest['name']}, {nearest['km_from_path']} km from my path", **{k: nearest[k] for k in ("name", "km_from_path")}))
    T = sorted(pts, key=lambda p: p["temp_c"])
    if T[-1]["temp_c"] - T[0]["temp_c"] >= 3:
        out.append(dict(kind="coldest", text=f"My coldest moment: {T[0]['temp_c']} °C over {label(T[0])}, {when(tkey(T[0]))}", temp_c=T[0]["temp_c"]))
        out.append(dict(kind="warmest", text=f"My warmest moment: {T[-1]['temp_c']} °C over {label(T[-1])}, {when(tkey(T[-1]))}", temp_c=T[-1]["temp_c"]))
    A = sorted([p for p in pts if p.get("aqi") is not None], key=lambda p: p["aqi"])
    if A:
        out.append(dict(kind="cleanest", text=f"My cleanest air: AQI {A[0]['aqi']} over {label(A[0])}, {when(tkey(A[0]))}", aqi=A[0]["aqi"]))
        if A[-1]["aqi"] >= 101: out.append(dict(kind="dirtiest", text=f"My dirtiest air: AQI {A[-1]['aqi']} ({aq_band(A[-1]['aqi'])}) over {label(A[-1])}, {when(tkey(A[-1]))}", aqi=A[-1]["aqi"]))
        bad = max(0, sum(1 for p in A if p["aqi"] >= 151) - 1)
        if bad: out.append(dict(kind="unhealthy_hours", text=f"I spent {bad} hours carrying unhealthy air (AQI 151+)", hours=bad))
        ha = ((here or {}).get("air_quality") or {}).get("now_aqi")
        if ha is not None:
            dirt = round(100 * sum(1 for p in A if p["aqi"] < ha) / len(A)); clean = round(100 * sum(1 for p in A if p["aqi"] > ha) / len(A))
            if max(dirt, clean) >= 50:
                out.append(dict(kind="here_vs_journey", text=(f"The air at the clicked spot (AQI {ha}) is dirtier than {dirt}% of my journey" if dirt >= clean else f"The air at the clicked spot (AQI {ha}) is cleaner than {clean}% of my journey"), aqi=ha, percent=max(dirt, clean)))
    W = max(pts, key=lambda p: p["wind_kmh"])
    out.append(dict(kind="fastest", text=f"My fastest moment: {W['wind_kmh']} km/h over {label(W)}, {when(tkey(W))}", wind_kmh=W["wind_kmh"]))
    rain = round(sum(p["rain_mmh"] for p in pts if p["temp_c"] > 1), 1); snow = round(sum(p["rain_mmh"] for p in pts if p["temp_c"] <= 1), 1)
    if rain >= .5: out.append(dict(kind="rain", text=f"About {rain} mm of rain fell around me on the way", mm=rain))
    if snow >= .5: out.append(dict(kind="snow", text=f"I passed through snow - about {snow} mm of water fell as snow or sleet around me", mm=snow))
    seas = []
    for p in pts:
        if p.get("marine") and p.get("region") and p["region"] not in seas: seas.append(p["region"])
    if seas: out.append(dict(kind="seas", text="Seas I crossed: " + ", ".join(seas), seas=seas))
    return out

def journey_both(q):
    """One click, one continuous life: the past 72 h that brought this air here (analysis winds), then the next 72 h (forecast).
    Timeline key hours_ago runs 144 -> 0 in play order; rel_h is hours relative to now (-72 .. +72)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        rb, rf = ex.map(lambda d: journey({"queryStringParameters": dict(q, dir=d)}), ("back", "forward"))
    if rb["statusCode"] != 200: return rb
    B = json.loads(rb["body"]); F = json.loads(rf["body"]) if rf["statusCode"] == 200 else None
    MID = 72.0; Kb = B["total_km"]
    pts = []
    for p in B["points"]: pts.append(dict(p, hours_ago=round(p["hours_ago"] + MID, 2), rel_h=-p["hours_ago"], hours_ahead=round(MID - p["hours_ago"], 2)))
    for p in (F["points"][1:] if F else []):
        pts.append(dict(p, hours_ago=p["hours_ago"], rel_h=p["hours_ahead"], hours_ahead=round(MID + p["hours_ahead"], 2), km_from_start=round(p["km_from_start"] + Kb, 1)))
    ev = [dict(e, hours_ago=round(e["hours_ago"] + MID, 2), rel_h=-e["hours_ago"]) for e in B["events"]]
    seen = {e["text"] for e in ev if e["kind"] == "region"}
    for e in (F["events"] if F else []):
        if e["kind"] == "region" and e["text"] in seen: continue
        ev.append(dict(e, rel_h=e.get("hours_ahead", MID - e["hours_ago"])))
    here = B.get("here")
    if here: ev.append(dict(hours_ago=MID, rel_h=0, lat=B["points"][-1]["lat"], lon=B["points"][-1]["lon"], kind="here", text=f"over {B['name']} right now - {here['headline']}"))
    ev.sort(key=lambda e: -e["hours_ago"])
    st = [dict(s, hours_ago=round(s["hours_ago"] + MID, 2), rel_h=-s["hours_ago"]) for s in B["places"]]
    for s in (F["places"] if F else []):
        if any(x["name"] == s["name"] and abs(x["hours_ago"] - s["hours_ago"]) < 4 for x in st): continue
        st.append(dict(s, rel_h=s["hours_ahead"]))
    st.sort(key=lambda s: -s["hours_ago"])
    pb, pf = B["passport"], (F["passport"] if F else {})
    passport = dict(countries=sorted(set(pb.get("countries", [])) | set(pf.get("countries", []))),
                    towns_15k_plus=pb.get("towns_15k_plus", 0) + pf.get("towns_15k_plus", 0), people_in_towns=pb.get("people_in_towns", 0) + pf.get("people_in_towns", 0),
                    came_from_km=round(Kb), goes_on_km=round(F["total_km"]) if F else 0)
    swarm = [b + (f[1:] if F else []) for b, f in zip(B["swarm"], F["swarm"] if F else [[]] * len(B["swarm"]))]
    nearest = None if st else nearest_town_to_path([p["lat"] for p in pts], [p["lon"] for p in pts], [p["rel_h"] for p in pts])
    settlements, seen_s = [], set()
    for p in pts:
        pl = p.get("place")
        if pl and pl["km"] <= 30 and pl["name"] not in seen_s:
            seen_s.add(pl["name"]); settlements.append(dict(pl, rel_h=p["rel_h"]))
    extra = dict(discoveries=discoveries(pts, lambda p: p["rel_h"], here, nearest, st), start_label=label(pts[0]), end_label=label(pts[-1]),
                 here_label=B["name"], settlements=settlements, nearest_town=nearest)
    return resp(200, dict(name=B["name"], direction="both", mid_hours=MID, here=here, downwind=F["downwind"] if F else None,
        release_utc=B["release_utc"], now_utc=B["arrival_utc"], arrival_utc=F["arrival_utc"] if F else B["arrival_utc"], level=B["level"],
        data_cycles=B["data_cycles"], total_km=round(Kb + (F["total_km"] if F else 0), 1), past_km=Kb, future_km=F["total_km"] if F else 0,
        points=pts, events=ev, places=st, passport=passport, swarm=swarm, swarm_spread_km=B["swarm_spread_km"], source=B["source"], **extra))

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

def aq_band(a):
    if a is None: return None
    return ("good" if a <= 50 else "moderate" if a <= 100 else "unhealthy for sensitive groups" if a <= 150 else
            "unhealthy" if a <= 200 else "very unhealthy" if a <= 300 else "hazardous")

def air_quality(lats, lons, times):
    """Air quality at each (lat, lon, unix time): CAMS (Copernicus Atmosphere Monitoring Service) via the Open-Meteo
    air-quality API (CC BY 4.0). US AQI, PM2.5, PM10. One batched request; None where unavailable."""
    import urllib.request, urllib.parse, calendar
    if not len(lats): return []
    qs = urllib.parse.urlencode(dict(latitude=",".join(f"{float(x):.2f}" for x in lats), longitude=",".join(f"{((float(y) + 180) % 360) - 180:.2f}" for y in lons),
                                     hourly="pm2_5,pm10,us_aqi", past_days=4, forecast_days=5, timezone="GMT"))
    try:
        raw = json.loads(urllib.request.urlopen(urllib.request.Request(AQ_URL + "?" + qs, headers={"User-Agent": "biography-of-a-breath"}), timeout=8).read())
    except Exception as e:
        print(json.dumps({"aq": "unavailable", "error": repr(e)[:200]})); return [None] * len(lats)
    raw = raw if isinstance(raw, list) else [raw]
    out = []
    for d, t in zip(raw + [None] * (len(lats) - len(raw)), times):
        h = (d or {}).get("hourly") or {}; ts = h.get("time") or []
        if not ts: out.append(None); continue
        k = int(round((float(t) - calendar.timegm(time.strptime(ts[0], "%Y-%m-%dT%H:%M"))) / 3600))
        if not 0 <= k < len(ts): out.append(None); continue
        g = lambda n: (lambda v: None if v is None else round(float(v), 1))((h.get(n) or [None] * len(ts))[k])
        a = g("us_aqi"); out.append(None if a is None else dict(aqi=int(round(a)), pm25=g("pm2_5"), pm10=g("pm10")))
    return out

def feels(p):
    """How the air itself feels at a moment - derived only from the data, for Puff to put into words."""
    f, a = [], p.get("aqi"); k = int(abs(p.get("hours_ago", 0))) // 3
    pick = lambda opts: opts[k % len(opts)]
    if a is not None:
        if a >= 201: f.append(pick(["thick with smoke and pollution - choking", "so heavy with smoke I can hardly breathe", "grey, acrid and suffocating"]))
        elif a >= 151: f.append(pick(["heavy, hazy and polluted", "murky and grey with haze", "stale and smoky, unhealthy to breathe", "tasting of dust and smoke"]))
        elif a >= 101: f.append(pick(["hazy, slightly dirty air", "a little grimy and dull", "faintly smoky haze"]))
        elif a <= 50: f.append(pick(["clean, fresh, light air", "crisp and clear", "light and clean, easy to breathe"]))
    if p["rain_mmh"] >= 2.5: f.append("drenched, washed by rain")
    elif p["rain_mmh"] >= .2: f.append("damp with drizzle")
    if p["rh"] >= 80 and p["temp_c"] >= 24: f.append("sticky and humid")
    elif p["rh"] <= 25: f.append("very dry")
    if p["temp_c"] >= 35: f.append("hot and sluggish")
    elif p["temp_c"] <= 5: f.append("cold and sharp")
    if p["wind_kmh"] >= 30: f.append("rushing, tumbling in strong wind")
    elif p["wind_kmh"] <= 5: f.append("barely moving, lingering")
    if not p["land"]: f.append("salty sea air over open water")
    return f

def rain_word(rate, total=None):
    """Plain-language rain intensity (AMS rate bands; daily totals for the 24 h windows)."""
    if rate >= 7.6 or (total or 0) >= 35: return "heavy rain"
    if rate >= 2.5 or (total or 0) >= 10: return "moderate rain"
    if rate >= 0.2 or (total or 0) >= 1: return "light rain"
    return "dry"

def here_forecast(lat, lon):
    """Local forecast for the clicked spot itself (NOAA GFS, ~50 km grid cell): now, next 24 h, 24-48 h, 48-72 h."""
    D = cube("cube/forecast.npz"); F = Field(D); T = F.T; la, lo = np.array([lat]), np.array([lon % 360])
    rates = [float(F.bil(D["prate"][k], la, lo)[0]) * 3600.0 for k in range(len(T))]          # mm/h, mean over the 6 h after T[k]
    now = time.time(); k0 = int(np.clip(np.searchsorted(T, now, side="right") - 1, 0, len(T) - 1))
    def val(name, k): return None if name not in D else float(F.bil(D[name][k], la, lo)[0])
    def win(h0, h1):
        ks = [k for k in range(len(T)) if h0 <= (T[k] - T[k0]) / 3600 < h1]
        if not ks: return None
        tot = sum(rates[k] * 6 for k in ks); mx = max(rates[k] for k in ks); kmx = max(ks, key=lambda k: rates[k])
        lt = (T[kmx] + 3 * 3600 + lon / 15 * 3600) % 86400 / 3600
        g = [val("gust", k) for k in ks]; g = [x for x in g if x is not None and x == x]
        return dict(rain_total_mm=round(tot, 1), heaviest_rate_mm_per_hour=round(mx, 1), rain=rain_word(mx, tot),
                    wettest_part_of_day=part_of_day(lt) if mx >= .2 else None,
                    temp_min_c=round(min(val("t2m", k) for k in ks) - 273.15, 1), temp_max_c=round(max(val("t2m", k) for k in ks) - 273.15, 1),
                    max_gust_kmh=round(max(g) * 3.6) if g else None)
    u, v = val("u10", k0), val("v10", k0); r0 = rates[k0]
    t_loc = (now + lon / 15 * 3600) % 86400 / 3600
    out = dict(lat=round(lat, 4), lon=round(lon, 4), forecast_cycle_utc=time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(T[0])),
               local_time=f"{int(t_loc):02d}:{int(t_loc % 1 * 60):02d}", part_of_day=part_of_day(t_loc),
               now=dict(rain_mm_per_hour=round(r0, 1), rain=rain_word(r0), temp_c=round(val("t2m", k0) - 273.15, 1),
                        humidity_pct=round(val("rh2m", k0)), wind_kmh=round(math.hypot(u, v) * 3.6, 1)),
               next_24h=win(0, 24), from_24_to_48h=win(24, 48), from_48_to_72h=win(48, 72),
               note="model forecast for the ~50 km grid cell around this spot")
    aqs = air_quality([lat] * 9, [lon] * 9, [now + 3 * 3600 * i for i in range(9)])
    if aqs and aqs[0]:
        worst = max((x for x in aqs if x), key=lambda x: x["aqi"])
        out["air_quality"] = dict(now_aqi=aqs[0]["aqi"], now=aq_band(aqs[0]["aqi"]), pm25_now=aqs[0]["pm25"], worst_next_24h_aqi=worst["aqi"], worst_next_24h=aq_band(worst["aqi"]),
                                  source="CAMS via Open-Meteo")
    out["headline"] = _here_headline(out); return out

def _here_headline(h):
    n, a, b = h["now"], h["next_24h"] or {}, h["from_24_to_48h"] or {}
    parts = [("Raining here now" + (f" ({n['rain_mm_per_hour']} mm/h)" if n["rain_mm_per_hour"] >= .1 else "")) if n["rain"] != "dry" else f"Dry here now, {n['temp_c']} °C"]
    if a.get("rain") and a["rain"] != "dry": parts.append(f"next 24 h: {a['rain']}, {a['rain_total_mm']} mm")
    if b.get("rain") and b["rain"] != "dry": parts.append(f"the day after: {b['rain']}, {b['rain_total_mm']} mm")
    if len(parts) == 1: parts.append("no rain expected in the next 48 h")
    aq = h.get("air_quality")
    if aq: parts.append(f"air quality {aq['now']} (AQI {aq['now_aqi']})" + (f", up to AQI {aq['worst_next_24h_aqi']} in 24 h" if aq["worst_next_24h_aqi"] - aq["now_aqi"] >= 25 else ""))
    return " · ".join(parts)

def journey(event):
    q = (event or {}).get("queryStringParameters") or {}
    if q.get("dir") not in ("back", "forward"): return journey_both(q)
    try:
        lat, lon = float(q["lat"]), float(q["lon"]); assert -85 < lat < 85 and -180 <= lon <= 180
    except Exception:
        return resp(400, {"error": "pass lat (-85..85) and lon (-180..180)"})
    lev = "10" if q.get("level") == "10" else "850"
    fwd = q.get("dir") == "forward"
    D = cube("cube/forecast.npz" if fwd else "cube/latest.npz"); F = Field(D)
    ang = np.arange(24) * 2*math.pi/24; rk = 25 + 35 * (np.arange(24) % 3)
    la0 = np.concatenate([[lat], lat + rk/111.0*np.cos(ang)])
    lo0 = np.concatenate([[lon], lon + rk/(111.0*max(.2, math.cos(math.radians(lat))))*np.sin(ang)])
    steps = rewind(F, la0, lo0 % 360, lev, forward=fwd)
    ts = np.array([s[0] for s in steps]); A = np.array([s[1] for s in steps]); O = (np.array([s[2] for s in steps]) + 180) % 360 - 180
    a, o = A[:, 0], O[:, 0]
    temp = np.array([float(F.at("t2m", t, np.array([x]), np.array([y % 360]))[0]) - 273.15 for t, x, y in zip(ts, a, o)])
    rh = np.array([float(F.at("rh2m", t, np.array([x]), np.array([y % 360]))[0]) for t, x, y in zip(ts, a, o)])
    rain = np.array([float(F.rain(t, np.array([x]), np.array([y % 360]))[0]) for t, x, y in zip(ts, a, o)])
    land = np.array([float(F.at("land", t, np.array([x]), np.array([y % 360]))[0]) > .5 for t, x, y in zip(ts, a, o)])
    def opt(name, t, x, y):
        if name not in D: return None
        v = float(F.at(name, t, np.array([x]), np.array([y % 360]))[0]); return None if v != v else v
    def opt_step(name, t, x, y):                          # 6-hourly categorical fields (snow): no time interpolation
        if name not in D: return None
        k = int(np.clip(np.searchsorted(F.T, t, side="right") - 1, 0, len(F.T) - 1)); v = float(F.bil(D[name][k], np.array([x]), np.array([y % 360]))[0])
        return None if v != v else v
    gust = [opt("gust", t, x, y) for t, x, y in zip(ts, a, o)]; cape = [opt("cape", t, x, y) for t, x, y in zip(ts, a, o)]
    vis = [opt("vis", t, x, y) for t, x, y in zip(ts, a, o)]; snow = [opt_step("snow", t, x, y) for t, x, y in zip(ts, a, o)]
    TW = load("ref/places.npz")
    def near(x, y):
        d = hav(TW["lat"], TW["lon"], x, y); j = int(np.argmin(d))
        return dict(name=clean_name(TW["name"][j]), country=COUNTRY.get(str(TW["country"][j]), str(TW["country"][j])), km=round(float(d[j])), population=realpop(TW["pop"][j])) if d[j] <= 60 else None
    seg = np.concatenate([[0], hav(a[:-1], o[:-1], a[1:], o[1:])]); kmc = np.cumsum(seg)
    hours = (ts[-1] - ts) / 3600.0                      # timeline key, 72 -> 0 in play order
    ahead = (ts - ts[0]) / 3600.0                       # forward mode: hours after release
    pts = [dict(hours_ago=round(float(hours[i]), 2), hours_ahead=round(float(ahead[i]), 2), lat=round(float(a[i]), 4), lon=round(float(o[i]), 4),
                km_from_start=round(float(kmc[i]), 1), wind_kmh=round(float(seg[i+1] if i+1 < len(seg) else seg[i]), 1),
                temp_c=round(float(temp[i]), 1), rh=round(float(rh[i])), rain_mmh=round(float(rain[i]), 2), land=bool(land[i]),
                region=region_name(float(a[i]), float(o[i]))[0], marine=region_name(float(a[i]), float(o[i]))[1],
                gust_kmh=None if gust[i] is None else round(gust[i] * 3.6), visibility_km=None if vis[i] is None else round(vis[i] / 1000, 1),
                convective_energy_jkg=None if cape[i] is None else round(cape[i]), snowfall=None if snow[i] is None else snow[i] >= .5,
                near=near(float(a[i]), float(o[i]))) for i in range(len(a))]
    samp = list(range(0, len(pts), 3)) + ([len(pts) - 1] if (len(pts) - 1) % 3 else [])
    AQ = air_quality([pts[i]["lat"] for i in samp], [pts[i]["lon"] for i in samp], [float(ts[i]) for i in samp])
    for i, p in enumerate(pts):
        q_ = AQ[min(range(len(samp)), key=lambda n: abs(samp[n] - i))] if AQ else None
        p.update(aqi=q_["aqi"] if q_ else None, pm25=q_["pm25"] if q_ else None, pm10=q_["pm10"] if q_ else None, air=aq_band(q_["aqi"]) if q_ else None)
        p["feels"] = feels(p)
    gs = list(range(0, len(pts), 6)) + ([len(pts) - 1] if (len(pts) - 1) % 6 else [])
    GN = place_names([pts[i]["lat"] for i in gs], [pts[i]["lon"] for i in gs])
    for i, p in enumerate(pts):
        n_ = min(range(len(gs)), key=lambda n: abs(gs[n] - i)); p["place"] = GN[n_] if abs(gs[n_] - i) <= 3 else None
    for p in pts:                                          # local hazards at this point and this hour only
        hz = []
        if (p["aqi"] or 0) >= 151: hz.append(f"{aq_band(p['aqi'])} air · AQI {p['aqi']}")
        if p["snowfall"]: hz.append("snowfall likely")
        if p["rain_mmh"] >= 7.6: hz.append(f"heavy rain {p['rain_mmh']} mm/h")
        if (p["convective_energy_jkg"] or 0) >= 1000 and p["rain_mmh"] >= .2: hz.append("thunderstorm risk")
        if (p["gust_kmh"] or 0) >= 70: hz.append(f"strong gusts {p['gust_kmh']} km/h")
        if p["visibility_km"] is not None and p["visibility_km"] < 1: hz.append(f"poor visibility {p['visibility_km']} km")
        if p["temp_c"] >= 40: hz.append("extreme heat")
        if p["temp_c"] <= -25: hz.append("extreme cold")
        p["hazards"] = hz
    events, last_region, last_t, seen_regions = [], None, None, set()
    for i, p in enumerate(pts):
        if p["region"] and p["region"] != last_region and p["region"] not in seen_regions and (not events or events[-1]["hours_ago"] - p["hours_ago"] >= 3):
            seen_regions.add(p["region"])
            events.append(dict(hours_ago=p["hours_ago"], hours_ahead=p["hours_ahead"], lat=p["lat"], lon=p["lon"], kind="region", text=(f"over the {p['region']}" if p["marine"] else f"crossing the {p['region']}")))
            last_region = p["region"]
        if p["rain_mmh"] >= .2 and (i == 0 or pts[i-1]["rain_mmh"] < .2):
            events.append(dict(hours_ago=p["hours_ago"], lat=p["lat"], lon=p["lon"], kind="rain", text=f"modelled rain near the path ({p['rain_mmh']} mm/h)"))
        if last_t is not None and abs(p["temp_c"] - last_t) >= 6:
            events.append(dict(hours_ago=p["hours_ago"], lat=p["lat"], lon=p["lon"], kind="temp", text=f"temperature now {p['temp_c']} °C")); last_t = p["temp_c"]
        if last_t is None: last_t = p["temp_c"]
    last_hz = {}
    for p in pts:
        for hz in p["hazards"]:
            key = hz.split()[0]
            if key not in last_hz or last_hz[key] - p["hours_ago"] >= 6:
                events.append(dict(hours_ago=p["hours_ago"], lat=p["lat"], lon=p["lon"], kind="hazard", text=hz)); last_hz[key] = p["hours_ago"]
    events.sort(key=lambda e: -e["hours_ago"])
    span = pts[0]["hours_ago"]
    for e in events: e.setdefault("hours_ahead", round(span - e["hours_ago"], 2))
    stops, passport = places_near(a, o, hours)
    for s in stops: s.update(hours_ago=pts[s["hour_index"]]["hours_ago"], hours_ahead=pts[s["hour_index"]]["hours_ahead"], temp_c=pts[s["hour_index"]]["temp_c"], rain_mmh=pts[s["hour_index"]]["rain_mmh"])
    stops.sort(key=lambda s: -s["hours_ago"])
    report = None
    if fwd:
        dw = downwind(a, o, ahead)
        for t in dw:
            pq = min(pts, key=lambda q: abs(q["hours_ahead"] - t["reached_in_hours"])); t["aqi_arriving"] = pq.get("aqi"); t["air_arriving"] = pq.get("air")
        report = dict(towns=len(dw), people=int(sum(t["population"] for t in dw)), first=[dict(t, population=realpop(t["population"])) for t in dw[:8]],
                      people_within_24h=int(sum(t["population"] for t in dw if t["reached_in_hours"] <= 24)),
                      towns_within_24h=sum(1 for t in dw if t["reached_in_hours"] <= 24),
                      people_within_48h=int(sum(t["population"] for t in dw if t["reached_in_hours"] <= 48)),
                      towns_list=[dict(t, population=realpop(t["population"]), people_estimate=t["population"]) for t in dw[:80]])
        if not dw: report["nearest_town"] = nearest_town_to_path(a, o, ahead)
    swarm = [[[round(float(O[i, k]), 4), round(float(A[i, k]), 4)] for i in range(len(ts))] for k in range(1, A.shape[1])]
    spread = float(np.median(hav(A[0, 1:], O[0, 1:], a[0], o[0])))
    name = q.get("name")
    if not name:
        P = load("ref/places.npz"); d = hav(P["lat"], P["lon"], lat, lon); j = int(np.argmin(d))
        coord = f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'}"
        near12 = np.nonzero(d <= 12)[0]
        if len(near12): j = int(near12[np.argmax(P["pop"][near12])])
        here_pl = (pts[0] if fwd else pts[-1]).get("place")
        name = clean_name(P["name"][j]) if d[j] <= 40 else (here_pl["name"] if here_pl and here_pl["km"] <= 25 else ((pts[0] if fwd else pts[-1])["region"] or coord))
    try: here = here_forecast(lat, lon)
    except Exception as e: here = None; print("here", repr(e))
    return resp(200, dict(name=name, direction="forward" if fwd else "back", downwind=report, here=here,
        release_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts[0])), level="850 hPa" if lev == "850" else "10 m",
        arrival_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts[-1])), data_cycles=len(D["times"]),
        total_km=round(float(kmc[-1]), 1), points=pts, events=events, places=stops, passport=passport,
        swarm=swarm, swarm_spread_km=round(spread), source="NOAA GFS 0.25° (AWS Open Data, noaa-gfs-bdp-pds) · air quality: CAMS via Open-Meteo (CC BY 4.0) · Overture Maps · Natural Earth"))



# ------------------------------------------------------------------ narration (Nova agent with tools)
BR = boto3.client("bedrock-runtime"); POLLY = boto3.client("polly")
MODEL = os.environ.get("NARRATOR_MODEL", "us.amazon.nova-pro-v1:0")
VOICE = os.environ.get("NARRATOR_VOICE", "Ruth")
SYSTEM = """You are Puff, a small, curious cloud of air. A listener just clicked a spot on Earth, and you are the air that
arrived there. Your job is to tell them the true story of your last three days on the wind.
You know nothing until you look: use the tools to explore your own journey (overview, any moment in time, the towns you
passed, the seas and regions you crossed, the rain you met). Explore freely, then decide for yourself which moments are
worth telling and how many (between 6 and 12), and call tell_story.
Write in the past tense, first person ("Three days ago I was drifting over..."), moving forward in time to the arrival,
which you tell in the present ("Now I'm here in ..."). Each line 12-28 words, vivid, warm, varied; no emojis.
Every fact you state (numbers, places, countries, weather) must come from what the tools returned. Never guess, and never
mention smoke, fire, pollution, storms, snow or anything the tools did not show you. Anchor each line to the hours_ago it
describes (0 for arrival).
Be efficient: call each tool at most once per moment; do not repeat calls you already made.
Make every line different: don't name the same region in more than two lines, mention towns you passed, and round
numbers to whole numbers (e.g. "44 km/h", "8 degrees"). Time words must match hours_ago: about 72 = "three days ago",
about 48 = "two days ago", about 24 = "yesterday" or "a day ago", otherwise say "N hours before I reached you"."""

SYSTEM_FWD = """You are Puff, a small, curious puff of wind. A listener just clicked a spot on Earth and released you there,
right now. Using the latest NOAA forecast, tell them where you will travel over the next three days and who will breathe
you next. You know nothing until you look: use the tools (overview with the downwind report, any future moment, the towns
you will pass, the seas and regions ahead). Open with the FIRST town in the downwind report, at exactly the hour it lists, then\nspread your moments across the WHOLE 72 hours - the far end of the journey matters most for people downwind.
Whenever you name a town with an hour, use that town's own hour from the tools. hours_from_now 0 is RIGHT NOW at the\nrelease point; 72 is three days from now, the far end. Each line's hours_from_now must be the moment it describes. Then choose 6-12 moments and call tell_story. Vary them: towns and how many people will breathe you, but also what
the air feels (wind, gusts, rain, temperature, night or day, sea or land) and any local hazards the tools report.
Speak in the future tense, first person ("In 6 hours I'll be drifting over ..."). It is a forecast: say "I'll" or "the
forecast says", never certainty about what will happen to people. Kindly mention how many people live in the towns you
reach first, because that is why this matters (smoke, a gas leak or pollen released here would follow the same path).
Each line 12-28 words, vivid, calm, warm; no emojis. Every number, place and weather fact must come from the tools;
never mention smoke, fire, pollution or storms as facts. Round numbers. Anchor each line with hours_from_now (0 = release).
Time words must match: about 24 = "tomorrow", 48 = "in two days", 72 = "in three days"; never say "ago" or "yesterday".
Be efficient: call each tool at most once per moment."""

def _tools_spec(fwd=False):
    if fwd:
        obj = lambda props, req: {"json": {"type": "object", "properties": props, "required": req}}
        return {"tools": [
            {"toolSpec": {"name": "journey_overview", "description": "Summary of your next 72 hours, including the downwind report (towns and people reached).", "inputSchema": obj({}, [])}},
            {"toolSpec": {"name": "moment", "description": "Where you'll be and the forecast weather around you a given number of hours from now (0-72).",
                          "inputSchema": obj({"hours_from_now": {"type": "number"}}, ["hours_from_now"])}},
            {"toolSpec": {"name": "towns_along_path", "description": "Towns within 25 km of your future path, in the order you reach them.", "inputSchema": obj({}, [])}},
            {"toolSpec": {"name": "events", "description": "Seas and regions you'll cross, rain you'll meet, big temperature changes.", "inputSchema": obj({}, [])}},
            {"toolSpec": {"name": "tell_story", "description": "Finish: your forecast story, earliest moment first.",
                          "inputSchema": obj({"lines": {"type": "array", "items": {"type": "object", "properties": {
                              "hours_from_now": {"type": "number"}, "text": {"type": "string"}}, "required": ["hours_from_now", "text"]}}}, ["lines"])}}]}
    return _tools_spec_back()

def _tools_spec_back():
    obj = lambda props, req: {"json": {"type": "object", "properties": props, "required": req}}
    return {"tools": [
        {"toolSpec": {"name": "journey_overview", "description": "Summary of your whole 72-hour journey.", "inputSchema": obj({}, [])}},
        {"toolSpec": {"name": "moment", "description": "Where you were and the weather around you at a given number of hours before arriving (0-72).",
                      "inputSchema": obj({"hours_ago": {"type": "number"}}, ["hours_ago"])}},
        {"toolSpec": {"name": "towns_along_path", "description": "Real towns within 25 km of your path, oldest first.", "inputSchema": obj({}, [])}},
        {"toolSpec": {"name": "events", "description": "Seas and regions you crossed, rain you met, big temperature changes.", "inputSchema": obj({}, [])}},
        {"toolSpec": {"name": "tell_story", "description": "Finish: your narration lines, oldest moment first.",
                      "inputSchema": obj({"lines": {"type": "array", "items": {"type": "object", "properties": {
                          "hours_ago": {"type": "number"}, "text": {"type": "string"}}, "required": ["hours_ago", "text"]}}}, ["lines"])}}]}

def _tool_impl(J):
    P = J["points"]; fwd = J.get("direction") == "forward"
    def nearest_town(la, lo):
        T = load("ref/places.npz"); d = hav(T["lat"], T["lon"], la, lo); i = int(np.argmin(d))
        return dict(name=clean_name(T["name"][i]), country=COUNTRY.get(str(T["country"][i]), str(T["country"][i])), km_away=round(float(d[i])), population=realpop(T["pop"][i])) if d[i] <= 60 else None
    ARRT = __import__("calendar").timegm(time.strptime(J["arrival_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    def local_clock(p):                          # local solar time at the point (from longitude), and part of day
        t = (ARRT - p["hours_ago"] * 3600 + p["lon"] / 15 * 3600) % 86400 / 3600
        return f"{int(t):02d}:{int(t % 1 * 60):02d}", part_of_day(t)
    def moment(hours_ago):
        h = float(min(P[0]["hours_ago"], max(0, hours_ago))); p = min(P, key=lambda q: abs(q["hours_ago"] - h))
        tkey = dict(hours_from_now=p["hours_ahead"]) if fwd else dict(hours_ago=p["hours_ago"])
        reg = p["region"] if (p.get("marine") or not p["land"] or not ((p.get("near") and p["near"]["km"] <= 40) or (p.get("place") and p["place"]["km"] <= 30))) else None
        return dict(**tkey, over="land" if p["land"] else "sea", region=reg, temp_c=p["temp_c"], humidity_pct=p["rh"],
                    rain_mm_per_hour=p["rain_mmh"], raining=p["rain_mmh"] >= .2, wind_kmh=p["wind_kmh"], km_travelled_so_far=p["km_from_start"],
                    gust_kmh=p.get("gust_kmh"), visibility_km=p.get("visibility_km"), local_hazards=p.get("hazards") or [],
                    nearest_town=nearest_town(p["lat"], p["lon"]), local_time=local_clock(p)[0], part_of_day=local_clock(p)[1],
                    air_quality=None if p.get("aqi") is None else dict(us_aqi=p["aqi"], level=p["air"], pm25=p["pm25"]), how_it_feels=p.get("feels") or [],
                    nearest_settlement=(p.get("place") if p.get("place") and p["place"]["km"] <= 30 else None))
    if fwd:
        return {
            "journey_overview": lambda a: dict(released_at=J["name"], release_time_utc=J["release_utc"], hours=72, total_km=round(J["total_km"]),
                                               countries=[COUNTRY.get(c, c) for c in J["passport"]["countries"]], weather_right_here=J.get("here"), downwind_report=dict({k: v for k, v in J["downwind"].items() if k != "towns_list"}, first=[dict(t, population=realpop(t["population"])) for t in J["downwind"].get("first", [])]),
                                               companion_breaths=len(J["swarm"]), start=moment(72)),
            "moment": lambda a: moment(72 - float(a.get("hours_from_now", 0))),
            "towns_along_path": lambda a: [dict(name=t["name"], country=COUNTRY.get(t["country"], t["country"]), hours_from_now=t["hours_ahead"], temp_c=t["temp_c"],
                                                raining=t["rain_mmh"] >= .2, km_from_path=t["dist_km"], population=realpop(t["population"])) for t in J["places"]],
            "events": lambda a: [dict(hours_from_now=e["hours_ahead"], what=e["text"]) for e in J["events"]]}
    return {
        "journey_overview": lambda a: dict(arrived_in=J["name"], arrival_time_utc=J["arrival_utc"], hours=72, total_km=round(J["total_km"]), weather_right_here=J.get("here"),
                                           countries=[COUNTRY.get(c, c) for c in J["passport"]["countries"]], towns_passed=J["passport"]["towns_15k_plus"],
                                           companion_breaths=len(J["swarm"]), companions_started_km_apart=J["swarm_spread_km"],
                                           start=moment(72)),
        "moment": lambda a: moment(a.get("hours_ago", 0)),
        "towns_along_path": lambda a: [dict(name=t["name"], country=COUNTRY.get(t["country"], t["country"]), hours_ago=t["hours_ago"], temp_c=t["temp_c"],
                                            raining=t["rain_mmh"] >= .2, km_from_path=t["dist_km"], population=realpop(t["population"])) for t in J["places"]],
        "events": lambda a: [dict(hours_ago=e["hours_ago"], what=e["text"]) for e in J["events"]]}

BANNED = ("smoke", "pollut", "ash", "toxic", "dust", "smog", "fire", "burn", "dirty", "health", "sick", "storm", "thunder", "snow", "lightning")
def clean_name(n):
    """'Braga (Maximinos, Sé e Cividade)' -> 'Braga': Overture parish-union names read badly aloud."""
    n = str(n).split(" (")[0].strip(); return n

def realpop(v):
    """Overture sometimes carries a bucketed placeholder (15,000 / 50,000 / 100,000 ...) instead of a census figure: treat those as unknown."""
    v = int(v or 0); return None if v <= 0 or v % 5000 == 0 else v

def part_of_day(t):
    return "night" if t < 5 or t >= 21 else "dawn" if t < 7 else "morning" if t < 12 else "afternoon" if t < 17 else "evening"
TOD = {"morning": (5, 12), "afternoon": (12, 18), "evening": (16, 22), "night": (19, 6), "tonight": (18, 6), "midnight": (22, 2), "dawn": (4, 8),
       "sunrise": (4, 8), "dusk": (16, 20), "sunset": (16, 20), "noon": (10, 14), "midday": (10, 14)}
def story_issues(story, J, fwd, hkey):
    """Reviewer, whole-story pass: claims about a moment (time of day, warm/cool, calm/windy, rain, trends) must match the data there."""
    import re
    P = J["points"]; key = "hours_ahead" if fwd else "hours_ago"
    arr = __import__("calendar").timegm(time.strptime(J["arrival_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    win = lambda h: [p for p in P if abs(p[key] - h) <= 3] or [min(P, key=lambda p: abs(p[key] - h))]
    at = lambda h: min(P, key=lambda p: abs(p[key] - h))
    dw = J.get("downwind") or {}; totals = [v for v in (dw.get("people"), dw.get("people_within_24h"), J["passport"].get("people_in_towns")) if v]
    hh = J.get("here") or {}; here_rain = any((hh.get(w) or {}).get("rain", "dry") != "dry" for w in ("now", "next_24h", "from_24_to_48h"))
    order = sorted(range(len(story)), key=lambda i: float(story[i].get(hkey, 0)) * (1 if fwd else -1)); out = {}
    town_names = {str(s["name"]).lower() for s in J.get("places", []) if s.get("name")} | \
                 {str((q.get("near") or {}).get("name")).lower() for q in P if (q.get("near") or {}).get("name")}
    towns_in = {i: {t for t in town_names if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", str(story[i].get("text", "")).lower())} for i in range(len(story))}
    for n, i in enumerate(order):
        txt = str(story[i].get("text", "")); low = txt.lower(); h = float(story[i].get(hkey, 0)); W = win(h); p = at(h)
        clock = lambda q: (arr - q["hours_ago"] * 3600 + q["lon"] / 15 * 3600) % 86400 / 3600
        why = ""
        for w, (a, b) in TOD.items():
            if re.search(rf"\b{w}\b", low):
                ok = any((a <= clock(q) < b) if a < b else (clock(q) >= a or clock(q) < b) for q in W if abs(q[key] - h) <= 1.5)
                if not ok: why = f"'{w}' is wrong: it is about {clock(p):.0f}:00 local time there ({part_of_day(clock(p))}) - the moment tool gives local_time"; break
        Q = [q["aqi"] for q in W if q.get("aqi") is not None] or [-1]
        if not why and Q != [-1] and not re.search(r"\b(?:us aqi|aqi|air quality index|pollution level|air quality)\s*(?:of\s*|at\s*|is\s*|was\s*|:\s*)?\d", low):
            for sent_ in re.split(r"(?<=[.!?;])\s+", low):
                if not re.search(r"\b(air|aqi|breathe?)\b", sent_): continue
                ws_ = re.findall(r"\b(unhealthy for sensitive groups|very unhealthy|unhealthy|moderate|hazardous)\b(?!\s+(?:breeze|wind|winds|gusts?|pace|speed|rain|drizzle|humidity|temperature|chill|warmth))", sent_) + \
                      re.findall(r"\b(good)\b(?=\s+(?:air|aqi))|(?<=air quality is )(good)\b|(?<=air quality was )(good)\b", sent_)
                ws_ = [w if isinstance(w, str) else next(x for x in w if x) for w in ws_]
                bad_w = [w_ for w_ in ws_ if all(aq_band(a) != w_ for a in Q)]
                if bad_w: why = f"the air quality here is '{aq_band(p.get('aqi'))}' (AQI {p.get('aqi')}), not '{bad_w[0]}'"; break
        T = [q["temp_c"] for q in W]; V = [q["wind_kmh"] for q in W]; G = [q.get("gust_kmh") or q["wind_kmh"] for q in W]; R = [q["rain_mmh"] for q in W]; H = [q["rh"] for q in W]
        rules = [(r"\bhot\b", max(T) >= 30, f"'hot' needs 30 °C or more; it is {p['temp_c']} °C"),
                 (r"\bwarm\b", max(T) >= 18, f"'warm' needs 18 °C or more; it is {p['temp_c']} °C"),
                 (r"\bmild\b", any(10 <= t <= 26 for t in T), f"'mild' doesn't fit {p['temp_c']} °C"),
                 (r"\b(cool|crisp|chilly|fresh and cool)\b", min(T) <= 22, f"'cool' doesn't fit {p['temp_c']} °C"),
                 (r"\b(cold|freezing|icy|frosty)\b", min(T) <= 8, f"'cold' doesn't fit {p['temp_c']} °C"),
                 (r"\b(humid|muggy|sticky|damp)\b", max(H) >= 65, f"'humid' needs humidity of 65% or more; it is {p['rh']}%"),
                 (r"\b(calm|still air|windless)\b", min(V) <= 8, f"'calm' doesn't fit {p['wind_kmh']} km/h of wind"),
                 (r"\b(rush\w*|rac(?:e|ing)|whip\w*|tumbl\w*|roar\w*|hurtl\w*)\b", max(V) >= 25 or max(G) >= 40, f"rushing needs a strong wind; it is {p['wind_kmh']} km/h"),
                 (r"\b(strong wind|windy|gusty|blustery|gale|howling)\b", max(V) >= 25 or max(G) >= 40, f"'windy' doesn't fit {p['wind_kmh']} km/h"),
                 (r"\b(choking|chok\w*|suffocat\w*|hard to breathe|gasp\w*|toxic|stifl\w*)\b", max(Q) >= 151, f"that needs unhealthy air (AQI 151+); the AQI here is {p.get('aqi')}"),
                 (r"\b(smok\w*|pollut\w*|smog\w*|haz[ey]|haze|dirty|grimy|soot\w*|unhealthy)\b", max(Q) >= 101, f"the air isn't polluted here (AQI {p.get('aqi')})"),
                 (r"\b(sea|seas|ocean|open water|over water|salty|salt air|waves)\b", any(q.get("marine") or ((not q["land"]) and not q.get("near") and not (q.get("place") and q["place"]["km"] <= 30)) for q in W), f"you are over land here ({label(p)}), not the sea"),
                 (r"\b(clean|pure|pristine|crystal)\b", (min(Q) <= 50 if Q != [-1] else not p["land"]), f"the air isn't clean here (AQI {p.get('aqi')})"),
                 (r"\b(rain|raining|drizzle|shower|showers|downpour|wet)\b", max(R) >= .1 or (h <= 1.5 and here_rain) or re.search(r"\b(no|without|not|dry|before the|after the)\b[^.]{0,20}\b(rain|drizzle|shower)", low),
                  f"there is no rain at this moment ({p['rain_mmh']} mm/h)")]
        if not why:
            for pat, ok, msg in rules:
                if re.search(pat, low) and not ok: why = msg; break
        if not why and n > 0:                    # trends against the previous moment in play order
            q0 = at(float(story[order[n - 1]].get(hkey, 0)))
            windy = re.search(r"\b(wind|breeze|gusts?|air speed)\b", low)
            up_w, dn_w = re.search(r"\b(picks? up|picking up|stronger|increas\w*|strengthen\w*|freshen\w*)\b", low), re.search(r"\b(dies? down|dying down|weaker|eases?|easing|slows?|slowing|calmer|softens?)\b", low)
            up_t, dn_t = re.search(r"\b(warms?|warming|warmer|rises?|rising|climbs?|climbing|heats? up)\b", low), re.search(r"\b(cools?|cooling|cooler|drops?|dropping|falls?|falling|dips?|dipping)\b", low)
            if windy and up_w and p["wind_kmh"] <= q0["wind_kmh"]: why = f"the wind does not pick up here: {q0['wind_kmh']} -> {p['wind_kmh']} km/h since the previous moment"
            elif windy and dn_w and p["wind_kmh"] >= q0["wind_kmh"]: why = f"the wind does not ease here: {q0['wind_kmh']} -> {p['wind_kmh']} km/h since the previous moment"
            elif up_t and not (windy and up_w) and p["temp_c"] <= q0["temp_c"]: why = f"it does not warm here: {q0['temp_c']} -> {p['temp_c']} °C since the previous moment"
            elif dn_t and not (windy and dn_w) and p["temp_c"] >= q0["temp_c"]: why = f"it does not cool here: {q0['temp_c']} -> {p['temp_c']} °C since the previous moment"
            elif STYLE_RULES and abs(float(story[order[n - 1]].get(hkey, 0)) - h) < 3: why = "two lines describe the same moment - keep one"
            elif STYLE_RULES:                                # the same town named twice within 6 hours reads as one moment told twice
                for j in order[:n]:
                    hj = float(story[j].get(hkey, 0)); twice = sorted(towns_in[i] & towns_in[j])
                    if twice and abs(hj - h) <= 6:
                        why = f"{twice[0].title()} is named in two lines {abs(hj - h):.0f} hours apart - keep one, or describe the second moment without naming it"; break
        if not why and totals:
            big = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{5,}\b", txt)]
            for x, u in re.findall(r"(\d+(?:\.\d+)?)\s*(thousand|lakh|million|crore)\b", low): big.append(float(x) * {"thousand": 1e3, "lakh": 1e5, "million": 1e6, "crore": 1e7}[u])
            if any(abs(v - t) <= .1 * t for v in big for t in totals) and not re.search(r"\b(downwind|breathe|along|in total|altogether|towns|combined)\b", low):
                why = "that figure is the total for all towns along the path, not the population of this place - say it as a total, or drop it"
        if why: out[i] = why
    return sorted(out.items())

FLAVOUR = ("sun", "sunlight", "sunny", "sunshine", "clear skies", "clear sky", "cloudy", "clouds", "overcast", "fog", "foggy", "mist", "misty", "starry", "stars", "significant", "major", "important", "notable", "remarkable", "dramatic", "stunning", "huge", "massive", "urban center", "urban centre",
           "landscape", "bustling", "busy", "sleepy", "sleeping", "ancient", "historic", "famous", "vibrant", "beautiful", "lush", "sprawling", "crowded",
           "peaceful", "majestic", "holy", "sacred", "golden", "fertile", "booming", "quaint", "charming", "lively", "thriving", "industrial", "rural")
OK_CAPS = {"I", "I'm", "I've", "I'd", "I'll", "Puff", "Celsius", "Earth", "North", "South", "East", "West", "Northern", "Southern", "Eastern", "Western"}
UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

def _spelled_numbers(low):
    import re
    out = []
    for m in re.finditer(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-](one|two|three|four|five|six|seven|eight|nine))?\b|\b(zero|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b(?!-)", low):
        if m.group(1): v = TENS[m.group(1)] + (UNITS[m.group(2)] if m.group(2) else 0)
        else: v = UNITS[m.group(3)]
        nxt = low[m.end():m.end() + 6]
        if re.match(r"\s+days?", nxt): v *= 24                       # "three days" -> 72 hours
        out.append((m.group(0), v))
    return out

def fix_hours(text, h, fwd_mode):
    """Repair, don't reject: the line's hour field is the truth, so hour counts written in the sentence are set to it."""
    import re
    if float(h or 0) <= 1.5: return text                                        # release/arrival line may speak about the days ahead here
    H = str(round(float(h)))
    pats = [r"(\bin (?:about |around |roughly |just |nearly )?)(\d+(?:\.\d+)?)( hours?\b)", r"(\b)(\d+(?:\.\d+)?)( hours? from now\b)",
            r"(\b(?:by|after|at) (?:about )?)(\d+(?:\.\d+)?)( hours?\b)"] if fwd_mode else \
           [r"(\b(?:about |around |roughly |just |nearly )?)(\d+(?:\.\d+)?)( hours? (?:ago|before|earlier)\b)"]
    for pat in pats: text = re.sub(pat, lambda m: m.group(1) + H + m.group(3), text, flags=re.I)
    text = re.sub(r"\b(?:N|X|n|x)(\s+hours?\b)", lambda m: H + m.group(1), text)
    return text

def check(text, evidence, evidence_low, line_hours=None, fwd_mode=False, town_hours=None, town_pop=None, local=None):
    """Reviewer: every number, place, country and weather claim must appear in what the agent's tools returned."""
    import re
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", evidence)]
    if local is not None:                        # numbers must also belong to THIS moment (+-3 h), the towns named here, or journey totals
        L = local(line_hours, text.lower()); nums = [v for v in nums if any(abs(abs(v) - abs(w)) <= max(0.051, 0.02 * abs(w)) or round(abs(w)) == abs(v) for w in L)] + [72, 24, 48] + [round(float(line_hours or 0)) + d for d in range(-3, 4)]
    near = lambda x: any(abs(abs(x) - abs(v)) <= max(0.051, 0.02 * abs(v)) or round(abs(v)) == abs(x) for v in nums)
    low = text.lower()
    SC = r"\s*(?:thousand|lakh|million|crore|billion)\b"
    for m_ in re.finditer(r"\d+(?:\.\d+)?", text.replace(",", "")):
        if re.match(SC, low.replace(",", "")[m_.end():]): continue          # scaled amounts are checked below
        if not near(float(m_.group(0))): return f"the number {m_.group(0)} does not belong to this moment (hour {round(line_hours or 0)}) or the places named in it - check it with the moment tool"
    for word, v in _spelled_numbers(low):
        i_ = low.find(word)
        if re.match(r"\s+days?\b", low[i_ + len(word):]): continue          # "two days" is checked as a time phrase below
        if re.match(SC, low[i_ + len(word):]): return f"write '{word} ...' as digits so it can be checked against your tools"
        if not near(float(v)): return f"'{word}' ({v}) is not in anything your tools returned"
    BAND = r"\b(unhealthy for sensitive groups|very unhealthy|unhealthy|moderate|good|hazardous)\b(?!\s+(?:breeze|wind|winds|gusts?|visibility|pace|speed|rain|drizzle|humidity))"
    for sent in re.split(r"(?<=[.!?;])\s+", low):                         # AQI band words must match the AQI given in the same sentence
        aqis = [int(x) for x in re.findall(r"\b(?:us aqi|aqi|air quality index|pollution level|air quality)\s*(?:of\s*|at\s*|is\s*|was\s*|:\s*)?(\d{1,3})\b", sent)]
        if not aqis: continue
        for w in re.findall(BAND, sent):
            if all(w != aq_band(a) for a in aqis): return f"AQI {aqis[0]} is '{aq_band(aqis[0])}', not '{w}'"
    SCALE ={"thousand": 1e3, "lakh": 1e5, "million": 1e6, "crore": 1e7, "billion": 1e9}
    big = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b", text)]
    for x, u in re.findall(r"(\d+(?:\.\d+)?)\s*(thousand|lakh|million|crore|billion)\b", low):
        v = float(x) * SCALE[u]; big.append(v)
        if not any(abs(v - w) <= .1 * w for w in nums if w >= 1000): return f"'{x} {u}' ({int(v):,}) is not in anything your tools returned"
    if town_pop and big and re.search(r"\b(home to|population|town of|city of|souls|residents|inhabitants|people live)\b", low):
        if "_townset" not in _C: _C["_townset"] = {str(n).lower() for n in load("ref/places.npz")["name"]}
        unknown = [w for w in re.findall(r"[A-Z][\w'’-]+(?:\s[A-Z][\w'’-]+)?", text) if w.lower() in _C["_townset"] and w.lower() not in town_pop and w not in OK_CAPS
                   and not any(w.lower() in n and n in low for n in town_pop)]
        if unknown: return f"you have no population for {unknown[0]} - only give populations the towns tools returned for that town"
        named = [n for n in town_pop if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", low)]
        if len(named) == 1 and not any(abs(v - town_pop[named[0]]) <= .05 * town_pop[named[0]] for v in big):
            return f"{named[0].title()}'s population in your tools is {town_pop[named[0]]:,}; don't give it another town's or a total's number"
    hrs = [v for v in nums]
    if fwd_mode and re.search(r"\b(ago|yesterday)\b", low): return "this is a forecast: no 'ago' or 'yesterday'"
    anchors = ((r"\bthree days ago\b", 72), (r"\btwo days ago\b", 48), (r"\byesterday\b", 24), (r"\b(a|one) day ago\b", 24)) if not fwd_mode else \
              ((r"\bin three days\b(?! ?(time|'s))", 72), (r"\bin two days\b", 48), (r"\btomorrow\b", 24), (r"\bin (a|one) day\b", 24))
    if line_hours is not None and line_hours <= 1.5: anchors = ()             # the release/arrival line may talk about the coming days right here
    for pat, target in anchors:
        m_ = re.search(pat, low); phrase = m_.group(0) if m_ else None
        if m_ and line_hours is not None and abs(line_hours - target) > 9:
            return f"'{phrase}' doesn't match this line's hour ({round(line_hours)}); say " + (f"'in {round(line_hours)} hours'" if fwd_mode else f"'{round(line_hours)} hours ago'") + " or move the line"
    if line_hours is not None and line_hours > 1.5:
        pats = [r"\bin (?:about |around |roughly |just |nearly |under |over )?(\d+(?:\.\d+)?) hours?\b", r"\b(\d+(?:\.\d+)?) hours? from now\b",
                r"\bat (\d+(?:\.\d+)?) hours?\b", r"\bat hour (\d+(?:\.\d+)?)\b", r"\bby (?:the )?(\d+)(?:st|nd|rd|th) hour\b", r"\b(\d+(?:\.\d+)?) hours? (?:in|later)\b"] if fwd_mode else \
               [r"\b(\d+(?:\.\d+)?) hours? ago\b"]
        for pat in pats:
            for x in re.findall(pat, low):
                if abs(float(x) - line_hours) > 2: return f"'{x} hours' doesn't match this line's own moment ({round(line_hours)} h) - set the line's hour to match, or fix the words"
        for word, v in _spelled_numbers(low):
            after = low[low.find(word) + len(word):]
            if (fwd_mode and re.search(rf"\bin (?:about |around )?{re.escape(word)}\b", low) or not fwd_mode and re.match(r"\s+(hours?|days?) ago", after)) \
               and re.match(r"\s+(hours?|days?)", after) and abs(v - line_hours) > 3:
                return f"'{word} ...' ({round(v)} h) doesn't match this line's own moment ({round(line_hours)} h)"
    m = re.search(r"\b(again|twice|thrice|second time|third time|once more|first time)\b", low)
    if m: return f"'{m.group(1)}' claims a repeat visit the tools did not show"
    for b in BANNED:
        if b in low and b not in evidence_low: return f"'{b}' was not in anything your tools returned"
    if STYLE_RULES and re.search(r"\bin (0|zero) hours?\b|\b(0|zero) hours? ago\b", low): return "don't say '0 hours' - say 'right now' or 'as I'm released'"
    if STYLE_RULES and fwd_mode and line_hours is not None and line_hours <= 1 and re.search(r"\b(right now|as i'm released|at the moment of my release)\b", low) and re.search(r"\bi'll\b|\bi will\b", low):
        return "this is the release moment: use the present tense ('Right now I'm drifting over...'), not 'I'll'"
    if line_hours is not None and line_hours > 2.5 and re.search(r"\b(an|one) hour (later|ago|before|after)\b|\bminutes? (later|ago)\b|\bmoments? (later|ago)\b", low):
        return "don't say 'an hour later' - each line is its own moment; say how many hours from now (or ago) it is, or just describe it"
    if re.search(r"[{}\[\]<>]|\b(?:N|X|Y)\s+(?:hours?|km|people|towns?)\b|\bTBD\b", text):
        return "this line still has a placeholder in it - write the real value from the tools"
    if STYLE_RULES and re.search(r"\bunknown population|population (?:is |was )?(?:unknown|null|not known)|population of (?:null|none)", low):
        return "don't mention a population you don't have - just leave it out"
    if STYLE_RULES and re.search(r"\b(an|some|one) (area|region|place|spot)\b|\bunnamed (location|place|spot)\b|\ba new (location|place|area|spot)\b|\bmillions of people\b", low): return "name the place (the region, sea or nearest town the moment tool returned) instead of 'an area'"
    for b in FLAVOUR:
        if re.search(rf"\b{b}\b", low) and b not in evidence_low: return f"'{b}' describes the place in a way your tools did not return - stick to the data"
    if town_hours:                                   # a town named next to an explicit hour must be reached at that hour
        said = [float(x) for x in re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", low)] + \
               [float(v) for w, v in _spelled_numbers(low) if re.search(rf"\b{re.escape(w)}\s+hours?\b", low)]
        for name, hs in town_hours.items():
            if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", low): continue
            if said and not any(abs(n - h) <= 0.6 for n in said for h in hs):
                return f"{name.title()} is reached at {', '.join(str(x) for x in sorted({round(h) for h in hs})[:3])} hours by your tools, not {', '.join(str(round(n)) for n in said)}"
            if line_hours is not None and min(abs(line_hours - h) for h in hs) > 3:
                return f"this line's moment ({round(line_hours)} h) is not when the path is near {name.title()} ({round(min(hs, key=lambda h: abs(h - line_hours)))} h)"
    if "_townset" not in _C: _C["_townset"] = {str(n).lower() for n in load("ref/places.npz")["name"]}
    for w in re.findall(r"[A-Z][\w'’-]+(?:\s[A-Z][\w'’-]+)?", text):
        for cand in {w, w.split()[0]}:
            if cand.lower() in _C["_townset"] and cand.lower() not in evidence_low and cand not in OK_CAPS: return f"'{cand}' is not a place your tools returned"
    for cname in set(COUNTRY.values()):
        if re.search(rf"\b{re.escape(cname)}\b", text) and cname.lower() not in evidence_low: return f"'{cname}' is not a country your tools returned"
    if not 6 <= len(text.split()) <= 40: return "line length"
    return ""

RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
STYLE_RULES = os.environ.get("STYLE_RULES", "0") == "1"   # off: style lives in the prompt; the reviewer only checks facts
FRAME_CALL = os.environ.get("FRAME_CALL", "0") == "1"     # off: the agent itself writes the opening, arrival and closing

def via_agentcore(q):
    """The narrator agent lives in Amazon Bedrock AgentCore Runtime; the API just invokes it."""
    import uuid, botocore.config
    c = boto3.client("bedrock-agentcore", config=botocore.config.Config(read_timeout=110, connect_timeout=5, retries={"max_attempts": 1}))
    t0 = time.time()
    r = c.invoke_agent_runtime(agentRuntimeArn=RUNTIME_ARN, runtimeSessionId=uuid.uuid4().hex + uuid.uuid4().hex[:8],
                               payload=json.dumps({k: q[k] for k in q if k in ("lat", "lon", "level", "dir", "half", "name")}).encode(), qualifier="DEFAULT")
    raw = r["response"].read() if hasattr(r.get("response"), "read") else b"".join(r.get("response", []))
    body = json.loads(raw)
    if isinstance(body, str): body = json.loads(body)
    if not isinstance(body, dict) or "lines" not in body: raise ValueError(f"unexpected runtime reply: {str(body)[:200]}")
    body["served_by"] = "Amazon Bedrock AgentCore Runtime"; body["runtime_seconds"] = round(time.time() - t0, 1)
    print(json.dumps({"agentcore": "ok", "seconds": body["runtime_seconds"], "lines": len(body["lines"])}))
    return resp(200, body, cache=0)

PUFF_VOICE = """You are Puff, a small wind spirit: you ARE the air the listener just clicked on. Tell the true story of your life on the wind,
in the first person, as a warm, curious storyteller. Your lines are spoken aloud.

HOW YOU WORK
- You know nothing until you look. Call storyboard first: it gives you about seven moments with every fact you may use (hour,
  local time, part of day, nearest town or settlement, weather, air quality, how it feels, how it changed). Call discoveries for
  surprising true facts about this journey. Use moment, towns_along_path, events or journey_overview for more detail when needed.
  Then call tell_story once.
- Every number, place, country and weather or air-quality word must come from what your tools returned. Never invent anything;
  if a fact is not there, leave it out. You have no cloud or sky data.

HOW YOU SPEAK
- One line per storyboard moment (skip at most two), each set to that moment's hour, 15 to 30 words.
- Write complete, natural sentences. how_it_feels gives you notes, not phrases to paste: turn them into your own words.
- Lead with how the air FEELS (how_it_feels, air_quality), not a weather report: smoky and heavy over a polluted city, washed clean
  by rain, salty over the sea, sticky in the heat, rushing in strong wind. At most two numbers per line, rounded: the AQI when the
  air is notable, a temperature, or a town's population.
- When the air is unhealthy (AQI 151+) or very clean (AQI 50 or less), say so plainly with its AQI. Use the band word that matches
  the number: good, moderate, unhealthy for sensitive groups, unhealthy, very unhealthy, hazardous.
- Name the town or settlement at each moment; over water, name the sea. Never say "a new location" or "an area".
- Every line must sound different: vary how lines begin and end, never repeat a description, and never list wind, temperature
  and air quality one after another.
- Weave one or two discoveries in where they fit; they make people curious.
- Time words must match the line's own hour.
"""
PUFF_PAST = """
YOUR PART: the FIRST half of this breath's life, the last 72 hours up to right now.
- OPENING at hours_ago 72: a hook. Right now you are passing over {name}, but you did not start there: three days ago you were
  over the first storyboard place. Invite the listener to follow you. (Present tense for right now, past tense for three days ago.)
- THE JOURNEY: past tense, moving towards now ("Two days ago I drifted over...", "13 hours ago...").
- ARRIVAL at hours_ago 0, present tense: how you reached {name}, and what it is like right here now, from weather_right_here in
  journey_overview (rain, temperature, air quality).
Time words: 72 = "three days ago", 48 = "two days ago", 24 = "yesterday"; otherwise "N hours ago".
"""
PUFF_FUTURE = """
YOUR PART: the SECOND half, the next 72 hours from the latest NOAA forecast. The listener has just heard you arrive at {name}.
- DEPARTURE at hours_from_now 1 to 3: where the wind takes you from {name}. Do not repeat the arrival.
- THE JOURNEY, future tense ("In 12 hours I'll be drifting over..."): who breathes you next - name the towns and how many people
  live there; if the land is empty, say so (discoveries).
- CLOSING at hours_from_now 70 to 72: where you end up, and one line that sums up your life as this breath.
It is a forecast: say "I'll" or "the forecast says". Time words: 24 = "tomorrow", 48 = "in two days", 72 = "in three days";
never "ago" or "yesterday".
"""

def frame_story(q):
    """The three lines that hold the story together - the opening hook, the arrival over the clicked spot and the closing -
    written by Nova from a small fact sheet of the whole journey and checked by the same reviewer. Runs beside the two halves."""
    import base64
    J = json.loads(journey({"queryStringParameters": {k: q[k] for k in q if k in ("lat", "lon", "level", "name")}})["body"])
    if "error" in J: return []
    here = J.get("here") or {}
    sheet = dict(clicked_place=J["name"], where_the_air_was_3_days_ago=J.get("start_label"), where_it_will_be_in_3_days=J.get("end_label"),
                 km_travelled_to_reach_here=round(J.get("past_km") or 0), km_it_will_travel_next=round(J.get("future_km") or 0),
                 weather_right_here_now=here.get("headline"), air_quality_right_here=here.get("air_quality"),
                 discoveries=[d["text"] for d in J.get("discoveries", [])],
                 towns_downwind_in_3_days=(J.get("downwind") or {}).get("towns"), people_downwind_in_3_days=(J.get("downwind") or {}).get("people"))
    ev = json.dumps(sheet, ensure_ascii=False); ev_low = ev.lower()
    spec = {"tools": [{"toolSpec": {"name": "frame_story", "description": "The opening, arrival and closing lines.", "inputSchema": {"json": {"type": "object", "properties": {
        "opening": {"type": "string"}, "arrival": {"type": "string"}, "closing": {"type": "string"}}, "required": ["opening", "arrival", "closing"]}}}}],
            "toolChoice": {"tool": {"name": "frame_story"}}}
    sysmsg = ("You are Puff, the air itself, speaking in the first person. Using ONLY the fact sheet, write three short spoken lines (12-30 words each):"
              f"\nopening - spoken before the journey: right now you are passing over {J['name']}, but three days ago you were over the place in"
              " where_the_air_was_3_days_ago; make the listener curious and invite them to follow you."
              f"\narrival - spoken as you reach {J['name']}: how far you came, and what it is like right here now (weather and air quality)."
              "\nclosing - spoken at the very end: where you will be in three days, and one discovery that sums up your life as this breath."
              " Never invent facts, places, numbers or descriptions that are not in the fact sheet. Use at most two numbers per line.")
    msgs = [{"role": "user", "content": [{"text": "Fact sheet:\n" + ev}]}]
    out = {}
    for attempt in range(3):
        try:
            r = BR.converse(modelId=MODEL, system=[{"text": sysmsg}], messages=msgs, toolConfig=spec, inferenceConfig={"maxTokens": 600, "temperature": 0.7})
        except Exception as e:
            print(json.dumps({"frame": "model error", "error": str(e)[:160]})); continue
        use = next((c["toolUse"] for c in r["output"]["message"]["content"] if "toolUse" in c), None)
        if not use: continue
        got = use.get("input") or {}; bad = {}
        for k in ("opening", "arrival", "closing"):
            if k in out: continue
            t = fix_hours(str(got.get(k, "")).strip(), 0, False)
            why = check(t, ev, ev_low) if t else "missing"
            if why: bad[k] = why
            else: out[k] = t
        if not bad: break
        msgs += [r["output"]["message"], {"role": "user", "content": [{"toolResult": {"toolUseId": use["toolUseId"], "status": "error", "content": [{"text":
                 "Rewrite only these lines, then call frame_story again with all three: " + "; ".join(f"{k}: {v}" for k, v in bad.items())}]}}]}]
    print(json.dumps({"frame": {k: bool(k in out) for k in ("opening", "arrival", "closing")}}))
    play = {"opening": 144.01, "arrival": 72.01, "closing": 0.0}
    lines = []
    for k in ("opening", "arrival", "closing"):
        if k not in out: continue
        audio = None
        for eng in ("generative", "neural"):
            try: audio = base64.b64encode(POLLY.synthesize_speech(Text=out[k], OutputFormat="mp3", VoiceId=VOICE, Engine=eng)["AudioStream"].read()).decode(); break
            except Exception as e: print("polly", eng, repr(e))
        lines.append(dict(hours_ago=play[k], kind="moment", role=k, half="frame", text=out[k], audio_mp3_b64=audio))
    return lines

def narrate(event):
    import base64, re
    from concurrent.futures import ThreadPoolExecutor
    q = (event or {}).get("queryStringParameters") or {}
    if RUNTIME_ARN and not os.environ.get("IN_AGENTCORE") and not q.get("local"):
        try: return via_agentcore(q)
        except Exception as e: print(json.dumps({"agentcore": "fallback", "error": repr(e)[:300]}))
    if q.get("dir") not in ("back", "forward"):
        fx = ThreadPoolExecutor(1); frame_f = fx.submit(frame_story, q) if FRAME_CALL else None
        with ThreadPoolExecutor(2) as ex:
            rb, rf = ex.map(lambda d: narrate({"queryStringParameters": dict(q, dir=d, half="1", local="1")}), ("back", "forward"))
        def why_bad(r):                                # None if the half is usable, else a short reason
            if r["statusCode"] != 200: return f"HTTP {r['statusCode']}: {str(r.get('body'))[:200]}"
            b = json.loads(r["body"]); n = len(b.get("lines") or [])
            if n < 3: return f"only {n} lines; last tools {[t.get('tool') for t in (b.get('agent_trace') or [])][-5:]}"
            return None
        halves = {"back": rb, "forward": rf}
        for d, name in (("back", "past"), ("forward", "future")):
            why = why_bad(halves[d])
            if why:                                    # re-run just this half once, locally
                print(json.dumps({"half_retry": name, "why": why}, ensure_ascii=False))
                halves[d] = narrate({"queryStringParameters": dict(q, dir=d, half="1", local="1")})
                again = why_bad(halves[d])
                if again: print(json.dumps({"half_retry_failed": name, "why": again}, ensure_ascii=False))
        rb, rf = halves["back"], halves["forward"]
        if rb["statusCode"] != 200: return rb
        B = json.loads(rb["body"]); F = json.loads(rf["body"]) if rf["statusCode"] == 200 else {"lines": [], "agent_trace": [{"tool": "half_error", "error": rf["body"][:300]}]}
        past = [dict(l, hours_ago=l["hours_ago"] + 72, half="past") for l in B["lines"]]
        now_said = any(abs(l["hours_ago"] - 72) <= 1.5 for l in past)                # one "right here, right now" line is enough
        try: frame = frame_f.result(timeout=60) if frame_f else []
        except Exception as e: frame = []; print(json.dumps({"frame": "failed", "error": repr(e)[:200]}))
        fx.shutdown(wait=False)
        if any(l.get("role") == "arrival" for l in frame):         # the arrival line replaces the halves' own 'now' lines
            past = [l for l in past if l["hours_ago"] > 73.5]; now_said = True
        lines = past + [dict(l, half="future") for l in F["lines"] if not (now_said and l["hours_ago"] >= 71.5)]
        lines = [l for l in frame if l.get("role") == "opening"] + lines + [l for l in frame if l.get("role") == "arrival"]
        lines.sort(key=lambda l: -l["hours_ago"])
        lines += [l for l in frame if l.get("role") == "closing"]
        for i, l in enumerate(lines): l["id"] = i; l["kind"] = "moment"
        lines = [l for l in lines]
        return resp(200, dict(model=MODEL, voice=VOICE, agent_trace=[dict(t, half="past") for t in B["agent_trace"]] + [dict(t, half="future") for t in F["agent_trace"]],
                              lines=lines), cache=0)
    J = json.loads(journey({"queryStringParameters": q})["body"])
    if "error" in J: return resp(400, J)
    fwd = J.get("direction") == "forward"
    impl, spec, system = _tool_impl(J), _tools_spec(fwd), (SYSTEM_FWD if fwd else SYSTEM) + ("\nYOU ARE THIS AIR. Speak in the first person about how you feel at each moment, using how_it_feels and air_quality:"
        " thick with smoke over a polluted city, washed clean by rain, salty over the sea, sticky in the heat, rushing in strong wind."
        " Air quality matters most to people: when it is unhealthy (AQI 151+) or very clean, say so plainly, with its AQI."
        " Use one or two numbers in most lines (the AQI, the temperature, a town's population) - never more than two - and let the feeling carry the rest."
        " Never reuse the same description twice: each moment feels different."
        " When the air is polluted, give its AQI in about half of those lines, and never end two lines the same way."
        "\nweather_right_here (in journey_overview) is the forecast for the spot the listener clicked: if rain is falling or coming"
        " there, say so in the line about that spot (hour 0) - it is what they will notice first."
        "\nStart by calling storyboard: write one line for each of its moments (skip at most two), in its order, with that moment's hour,"
        " using that moment's facts - the town, the hour, the local time, the weather and how it changed. Vary what each line notices.\nThe moment tool also gives local_time, part_of_day and the nearest_town with its population: use them for moments between"
        " towns, and never describe sky, sun or clouds - you have no cloud data. Say warm/cool/calm/windy only when the numbers at that moment show it.")
    system = PUFF_VOICE + (PUFF_FUTURE if fwd else PUFF_PAST).replace("{name}", J["name"])   # one coherent brief: how to speak, and this half's part
    SBN = []                                       # numbers the storyboard derived (changes since the previous moment), by hour
    def storyboard(a):
        k = "hours_from_now" if fwd else "hours_ago"; stops = {float(t["hours_ahead"] if fwd else t["hours_ago"]): t for t in J.get("places", [])}
        picks = []
        for t in range(0, 73, 12 if q.get("half") else 8):
            s_ = min(stops, key=lambda x: abs(x - t)) if stops else None
            h = s_ if s_ is not None and abs(s_ - t) <= 4 and s_ not in picks else float(t)
            if all(abs(h - x) >= 3 for x in picks): picks.append(h)
        picks.sort(reverse=not fwd); out, prev = [], None
        for h in picks:
            m = impl["moment"]({k: h}); st = stops.get(h)
            town = dict(name=st["name"], country=COUNTRY.get(st["country"], st["country"]), km_from_path=st["dist_km"], population=realpop(st["population"])) if st else (m.get("nearest_town") or m.get("nearest_settlement"))
            row = {k: m[k], "local_time": m["local_time"], "part_of_day": m["part_of_day"], "over": m["over"], "region": m["region"], "town": town,
                   "temp_c": m["temp_c"], "wind_kmh": m["wind_kmh"], "gust_kmh": m["gust_kmh"], "humidity_pct": m["humidity_pct"],
                   "rain_mm_per_hour": m["rain_mm_per_hour"], "visibility_km": m["visibility_km"], "local_hazards": m["local_hazards"], "km_travelled_so_far": m["km_travelled_so_far"],
                   "air_quality": m["air_quality"], "how_it_feels": m["how_it_feels"]}
            if out and town and out[-1].get("town") and out[-1]["town"]["name"] == town["name"]:
                row["same_town_as_previous_moment"] = "yes - the air has barely moved; say you are still lingering over it, don't introduce it as new"
            if prev:
                dt_, dw_ = round(m["temp_c"] - prev["temp_c"], 1), round(m["wind_kmh"] - prev["wind_kmh"], 1)
                row["since_previous_moment"] = dict(temperature=("warmer" if dt_ > 0.3 else "cooler" if dt_ < -0.3 else "about the same") + f" by {abs(dt_)} °C",
                                                    wind=("stronger" if dw_ > 1 else "weaker" if dw_ < -1 else "about the same") + f" by {abs(dw_)} km/h")
                SBN.append((float(m[k]), [abs(dt_), abs(dw_)]))
            out.append(row); prev = m
        return {"listener_clicked": J["name"], "how_to_use": "One line per moment, in this order, each line set to that moment's hour, using only that moment's facts. "
                "If a town's population is null it is unknown: don't give one.", "moments": out}
    impl["storyboard"] = storyboard
    if fwd: _near = (J.get("downwind") or {}).get("nearest_town")
    else: _near = None if J.get("places") else nearest_town_to_path([p["lat"] for p in J["points"]], [p["lon"] for p in J["points"]], [-p["hours_ago"] for p in J["points"]])
    DISC = discoveries(J["points"], (lambda p: p["hours_ahead"]) if fwd else (lambda p: -p["hours_ago"]), J.get("here"), _near, J.get("places"))
    impl["discoveries"] = lambda a: {"facts": DISC, "how_to_use": "Surprising, true facts about THIS journey. Weave one or two into your lines in your own words - they make people curious."}
    spec = {"tools": [{"toolSpec": {"name": "storyboard", "description": "CALL THIS FIRST. About ten moments spread across the whole 72 hours, each with every fact you may use: hour, local time, part of day, town, weather, and how it changed since the previous moment.",
                                    "inputSchema": {"json": {"type": "object", "properties": {}, "required": []}}}},
                      {"toolSpec": {"name": "discoveries", "description": "Surprising facts about this journey computed from its data: the emptiest stretch, the nearest people, coldest/warmest, cleanest/dirtiest air, fastest wind, rain, seas crossed.",
                                    "inputSchema": {"json": {"type": "object", "properties": {}, "required": []}}}}] + spec["tools"]}
    if False and q.get("half"):                      # (superseded by PUFF_PAST / PUFF_FUTURE)
        system += (("\nSTRUCTURE (you tell the FIRST half of the breath's life; another voice tells the future after you):"
                    f"\n1. OPENING at hours_ago 72: a hook. Right now you are passing over {J['name']}, but you did not start there - three days ago you were"
                    " somewhere else (name it from the storyboard). Invite the listener to come along. No time of day in this line."
                    "\n2. THE JOURNEY: your moments from 72 hours ago towards now, with one or two discoveries woven in."
                    f"\n3. ARRIVAL at hours_ago 0: how you came to reach {J['name']}, and what it is like right here now (weather_right_here).")
                   if not fwd else
                   ("\nSTRUCTURE (you tell the SECOND half; the listener has just heard you arrive here):"
                    f"\n1. DEPARTURE at hours_from_now 1-3: where the wind takes you from {J['name']} (do not repeat the arrival)."
                    "\n2. THE JOURNEY ahead, with one or two discoveries woven in - who breathes you next, or how empty the land is."
                    "\n3. CLOSING at hours_from_now 70-72: where you end up, and one line that sums up your life as this breath."))
    ask = "I just released you here. Where will you go, and who will breathe you next?" if fwd else "Tell me your story."
    msgs = [{"role": "user", "content": [{"text": f"I just clicked {J['name']} (lat {q.get('lat')}, lon {q.get('lon')}). {ask}"}]}]
    hkey = "hours_from_now" if fwd else "hours_ago"
    TP = {t["name"].lower(): realpop(t["population"]) for t in J.get("places", []) + ((J.get("downwind") or {}).get("first", []) if fwd else []) if realpop(t.get("population"))}
    for p in J["points"]:                            # nearest towns the moment tool can return, with their populations
        if p.get("near") and p["near"].get("population"): TP.setdefault(p["near"]["name"].lower(), int(p["near"]["population"]))
    PK = [(float(p["hours_ahead"] if fwd else p["hours_ago"]), p) for p in J["points"]]
    dw = J.get("downwind") or {}
    AGG = [72, 3, 24, 48, J["total_km"], len(J["passport"]["countries"]), J["passport"].get("towns_15k_plus", 0), J["passport"].get("people_in_towns", 0),
           len(J.get("swarm") or []), J.get("swarm_spread_km", 0)] + [v for k, v in dw.items() if isinstance(v, (int, float))]
    def _nums(o): return [x for v in o.values() for x in (_nums(v) if isinstance(v, dict) else [v] if isinstance(v, (int, float)) and not isinstance(v, bool) else [])] if isinstance(o, dict) else []
    HERE_N = _nums(J.get("here") or {})
    AGG += [x for d in DISC for x in _nums(d)]
    TOWNROWS = {}
    for t in J.get("places", []) + (dw.get("first", []) if fwd else []): TOWNROWS.setdefault(t["name"].lower(), []).append(t)
    ARR0 = __import__("calendar").timegm(time.strptime(J["arrival_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    def LOCAL(h, low):
        vals = list(AGG); h = float(h or 0)
        if h <= 1.5: vals += HERE_N + [24, 48, 72]                                   # the clicked spot's own forecast
        for k, p in PK:
            if abs(k - h) <= 3:
                c = (ARR0 - p["hours_ago"] * 3600 + p["lon"] / 15 * 3600) % 86400 / 3600      # local clock (the moment tool's local_time)
                vals += [int(c), int(c % 1 * 60), int(c) % 12 or 12]
                vals += [x for x in (p.get("aqi"), p.get("pm25"), p.get("pm10")) if x is not None]
                vals += [k, p["temp_c"], p["wind_kmh"], p["rh"], p["rain_mmh"], p["km_from_start"]] + \
                        [p.get(x) for x in ("gust_kmh", "visibility_km", "convective_energy_jkg") if p.get(x) is not None] + ([p["near"]["km"]] if p.get("near") else []) + \
                        ([p["near"]["population"]] if p.get("near") and p["near"].get("population") and re.search(rf"(?<!\w){re.escape(p['near']['name'].lower())}(?!\w)", low) else [])
        for name, rows in TOWNROWS.items():
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", low):
                for t in rows: vals += [t.get(x) for x in ("population", "hours_ahead", "hours_ago", "reached_in_hours", "temp_c", "dist_km", "rain_mmh") if t.get(x) is not None]
        for hh, vv in SBN:
            if abs(hh - h) <= 3: vals += vv
        return [float(v) for v in vals]
    TH = {}                                          # town -> hours (in the agent's own time key) from the journey itself
    if q.get("half") and not fwd: TH[J["name"].lower()] = [72.0]
    for t in J.get("places", []): TH.setdefault(t["name"].lower(), []).append(float(t["hours_ahead"] if fwd else t["hours_ago"]))
    for p in J["points"]:
        if p.get("near"): TH.setdefault(p["near"]["name"].lower(), []).append(float(p["hours_ahead"] if fwd else p["hours_ago"]))
    if fwd:
        for t in (J.get("downwind") or {}).get("first", []):
            if isinstance(t, dict) and "reached_in_hours" in t: TH.setdefault(t["name"].lower(), []).append(float(t["reached_in_hours"]))
    evidence, story, trace, revised, best = [], None, [], 0, []
    for turn in range(14):
        r = None
        for attempt in range(3):                 # Nova occasionally emits a malformed tool call (ModelErrorException): retry the turn
            try:
                r = BR.converse(modelId=MODEL, system=[{"text": system}], messages=msgs, toolConfig=spec,
                                inferenceConfig={"maxTokens": 2000, "temperature": 0.7}); break
            except Exception as e:
                if "ModelError" not in type(e).__name__ and "invalid sequence" not in str(e): raise
                print(json.dumps({"model_retry": attempt + 1, "error": str(e)[:160]})); trace.append({"tool": "model_retry", "error": str(e)[:120]})
        if r is None: break
        content = r["output"]["message"]["content"]; msgs.append({"role": "assistant", "content": content})
        uses = [c["toolUse"] for c in content if "toolUse" in c]
        if not uses:
            msgs.append({"role": "user", "content": [{"text": "Please finish by calling tell_story."}]}); continue
        results = []
        for u in uses:
            if u["name"] == "tell_story":
                story = [dict(l, text=fix_hours(str(l.get("text", "")), l.get(hkey, 0), fwd)) for l in (u["input"].get("lines", []) or []) if isinstance(l, dict)]
                ev = " ".join(evidence); ev_low = ev.lower()
                bad = [(i, check(l.get("text", ""), ev, ev_low, float(l.get(hkey, 0)), fwd, TH, TP, LOCAL)) for i, l in enumerate(story)]
                bad = [(i, why) for i, why in bad if why]
                seen_i = {i for i, _ in bad}; bad += [(i, why) for i, why in story_issues(story, J, fwd, hkey) if i not in seen_i]
                hs = [float(l.get(hkey, 0)) for l in story]
                hs_s = sorted(hs); gap = max([b - a for a, b in zip(hs_s, hs_s[1:])] or [0])
                popl = sum(1 for l in story if re.search(r"\b(population|residents|inhabitants|people live|home to)\b", str(l.get("text", "")).lower()))
                if STYLE_RULES and story and revised < 3 and len(story) > 12:
                    bad.append((len(story) - 1, f"you told {len(story)} moments; keep the best 6-12, spread across the journey"))
                opens = [" ".join(re.findall(r"[a-z']+", str(story[i].get("text", "")).lower())[:2]) for i in sorted(range(len(story)), key=lambda i: float(story[i].get(hkey, 0)))]
                runs = [n for n in range(2, len(opens)) if opens[n] == opens[n - 1] == opens[n - 2] and opens[n] not in ("in hours", "hours ago", "in about", "about hours", "by hours", "at hours", "after hours")]
                if STYLE_RULES and story and revised < 3 and runs:
                    bad.append((len(story) - 1, f"three lines in a row open with '{opens[runs[0]]}' - vary how the lines begin"))
                WX = r"°|\b(km/h|wind|breeze|gust\w*|rain\w*|drizzle|humid\w*|warm\w*|cool\w*|cold|hot|calm|chill\w*|sea|ocean|coast|storm|snow|fog|visibility|air|aqi|smok\w*|chok\w*|pollut\w*|haz[ey]|clean|fresh|salty|sticky|damp|drench\w*|breath\w*|lingering|rushing)\b"
                dry_ = sum(1 for l in story if not re.search(WX, str(l.get("text", "")).lower()))
                clocks_ = sum(1 for l in story if re.search(r"\b\d{1,2}:\d{2}\b", str(l.get("text", ""))))
                grams = {}
                for l in story:
                    w_ = re.findall(r"[a-z']+", str(l.get("text", "")).lower())
                    for g in {" ".join(w_[i:i + 3]) for i in range(len(w_) - 2)}: grams[g] = grams.get(g, 0) + 1
                rep_ = [g for g, c in grams.items() if c >= 3 and not re.match(r"^(in|hours|i'll|i will|i was|ago|i'm|over the|the air|i am|over|of|by|at)\b", g)
                        and not re.search(r"\b(hours ago|in india|of bengal|the bay|air quality of|a town of|a city of)\b", g)]
                if STYLE_RULES and story and revised < 3 and rep_:
                    bad.append((len(story) - 1, f"the phrase '{rep_[0]}' repeats in {grams[rep_[0]]} lines - say each moment in a fresh way"))
                dense_ = sum(1 for l in story if len(re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"\b\d+ hours?\b", "", str(l.get("text", ""))))) > 2)
                if STYLE_RULES and story and revised < 3 and dense_ > 2:
                    bad.append((len(story) - 1, f"{dense_} lines read like a data sheet (3+ numbers) - keep at most two numbers per line and say how the air FEELS (how_it_feels): smoky, washed by rain, salty, sticky, rushing"))
                if STYLE_RULES and story and revised < 3 and dry_ > 2:
                    bad.append((len(story) - 1, f"{dry_} lines say nothing about the air itself - give each line something you feel: wind, warmth or cold, rain, sea, calm"))
                if STYLE_RULES and story and revised < 3 and clocks_ > 2:
                    bad.append((len(story) - 1, "don't read out clock times line after line - say 'at dusk', 'deep in the night', 'by morning' instead; keep at most two exact times"))
                if STYLE_RULES and story and revised < 3 and gap > 24:
                    a_ = max(zip(hs_s, hs_s[1:]), key=lambda x: x[1] - x[0])
                    bad.append((len(story) - 1, f"nothing happens between hour {round(a_[0])} and hour {round(a_[1])}; add a moment in that stretch (use moment or towns_along_path)"))
                if STYLE_RULES and story and revised < 3 and popl > max(3, len(story) // 2):
                    bad.append((len(story) - 1, f"{popl} lines just recite a population; keep that for at most half, and give the others what the air feels: wind, gusts, rain, temperature, day or night, sea or land, local hazards"))
                if not STYLE_RULES and story and revised < 1 and q.get("half") and (min(hs) > 6 or max(hs) < 66):
                    bad.append((len(story) - 1, ("you are missing your " + ("opening (hours_ago 72) or arrival (hours_ago 0)" if not fwd else "departure (hours_from_now 1-3) or closing (hours_from_now 70-72)") +
                                                 f" - your lines cover {round(min(hs))}-{round(max(hs))} h; add them and call tell_story again with the full story")))
                if STYLE_RULES and story and revised < 3 and (len(story) < 6 or min(hs) > 12 or max(hs) < 60):
                    bad.append((len(story) - 1, f"the story only covers {round(min(hs))}-{round(max(hs))} h of the 72-hour journey; it must start within the first 12 hours and reach past hour 60 (call moment/towns_along_path for those hours)"))
                trace.append({"tool": "tell_story", "lines": len(story), "rejected": len(bad),
                              "reviewer": [{"line": story[i].get("text", ""), "hour": story[i].get(hkey), "reason": why} for i, why in bad]})
                drop_ = {i for i, _ in bad}; keep_ = [l for i, l in enumerate(story) if i not in drop_]
                if len(keep_) >= len(best): best = keep_                     # fallback if the agent never finishes cleanly
                keep_h = [float(l.get(hkey, 0)) for i, l in enumerate(story) if i not in {j for j, _ in bad}]
                cut_off = bool(bad) and (not keep_h or min(keep_h) > 12 or max(keep_h) < 60)
                if bad and (revised < 3 or (revised < 4 and cut_off)):   # revise with the reviewer's reasons (one extra try if the ending would be lost)
                    revised += 1
                    fb = "The reviewer found problems. Fix these (rewrite or add lines, using tools if needed), then call tell_story again with the full story:\n" + \
                         "\n".join(f"- line {i} \"{story[i]['text']}\": {why}" for i, why in bad)
                    print(json.dumps({"review": [{"text": story[i]["text"], "reason": why} for i, why in bad]}, ensure_ascii=False))
                    results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"text": fb}], "status": "error"}})
                    story = None
                else:
                    if bad: print(json.dumps({"dropped": [{"text": story[i]["text"], "reason": why} for i, why in bad]}, ensure_ascii=False))
                    drop = {i for i, _ in bad}; story = [l for i, l in enumerate(story) if i not in drop]
                    results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"text": "ok"}]}})
            else:
                try: out = impl[u["name"]](u.get("input") or {})
                except Exception as e: out = {"error": str(e)}
                evidence.append(json.dumps(out, ensure_ascii=False)); trace.append({"tool": u["name"], "input": u.get("input")})
                results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"json": {"result": out}}]}})
        msgs.append({"role": "user", "content": results})
        if story is not None: break
    if not story and best: story = best; trace.append({"tool": "fallback", "lines": len(best), "note": "agent did not finish cleanly; kept its last lines that passed review"})
    if story and len(story) > 12:              # still too long after revisions: keep 12 spread evenly in time
        story = sorted(story, key=lambda l: float(l.get(hkey, 0)))
        story = [story[round(i * (len(story) - 1) / 11)] for i in range(12)]
    for l in story or []:                      # player timeline key: 72 -> 0 in play order
        l["hours_ago"] = 72 - float(l.get(hkey, 0)) if fwd else float(l.get(hkey, 0))
    story = sorted(story or [], key=lambda l: -float(l.get("hours_ago", 0)))
    def voice(l):
        t = re.sub(r"\b\d{5,}\b", lambda m: f"{int(m.group(0)):,}", str(l["text"]).strip()); audio = None
        for eng in ("generative", "neural"):
            try:
                a = POLLY.synthesize_speech(Text=t, OutputFormat="mp3", VoiceId=VOICE, Engine=eng)
                audio = base64.b64encode(a["AudioStream"].read()).decode(); break
            except Exception as e: print("polly", eng, repr(e))
        h = float(l.get("hours_ago", 0))
        return dict(hours_ago=h, kind="arrive" if (h <= 0.5 and not fwd) else "moment", text=t, audio_mp3_b64=audio)
    with ThreadPoolExecutor(6) as ex: out = list(ex.map(voice, story))
    for i, l in enumerate(out): l["id"] = i
    return resp(200, dict(model=MODEL, voice=VOICE, agent_trace=trace, lines=out), cache=0)

def resp(code, body, cache=900):
    return {"statusCode": code, "headers": {"content-type": "application/json",
            "cache-control": f"public, max-age={cache}" if cache else "no-store"}, "body": json.dumps(body)}
