"""Run the LIVE journey API for a sample of places and compute the article's numbers from
whatever the current NOAA data says. Nothing here is precomputed: rerun it and the numbers change.
Usage: python tools/stats.py [places.csv]  ->  out/stats.json + out/stats.md
places.csv rows: name,lat,lon   (default: a spread of world cities, any list works)"""
import csv, json, statistics as st, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
API = open("backend/build/api_url.txt").read().strip().rstrip("/")
SAMPLE = """London,51.5074,-0.1278
New Delhi,28.6139,77.2090
Chennai,13.0827,80.2707
Mumbai,19.0760,72.8777
Lagos,6.5244,3.3792
Cairo,30.0444,31.2357
Nairobi,-1.2921,36.8219
Cape Town,-33.9249,18.4241
New York,40.7128,-74.0060
Mexico City,19.4326,-99.1332
Lima,-12.0464,-77.0428
Sao Paulo,-23.5505,-46.6333
Reykjavik,64.1466,-21.9426
Moscow,55.7558,37.6173
Dubai,25.2048,55.2708
Singapore,1.3521,103.8198
Tokyo,35.6762,139.6503
Sydney,-33.8688,151.2093
Auckland,-36.8485,174.7633
Honolulu,21.3069,-157.8583"""
rows = list(csv.reader(open(sys.argv[1]))) if len(sys.argv) > 1 else [r.split(",") for r in SAMPLE.splitlines()]

def run(r):
    name, lat, lon = r[0], r[1], r[2]
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "name": name})
    J = json.load(urllib.request.urlopen(f"{API}/?{q}", timeout=60))
    pts = J["points"]; regions = [e["text"] for e in J["events"] if e["kind"] == "region"]
    seas = [e["text"].replace("over the ", "") for e in J["events"] if e["kind"] == "region" and e["text"].startswith("over the")]
    return dict(name=name, km=J["total_km"], arrival_utc=J["arrival_utc"], start=dict(lat=pts[0]["lat"], lon=pts[0]["lon"], region=pts[0]["region"]),
                straight_km=None, countries=J["passport"]["countries"], towns=J["passport"]["towns_15k_plus"],
                stops=[p["name"] for p in J["places"]], regions=regions, seas=seas,
                tmin=min(p["temp_c"] for p in pts), tmax=max(p["temp_c"] for p in pts),
                rain_hours=sum(1 for p in pts if p["rain_mmh"] >= .2), companions_spread_km=J["swarm_spread_km"])

with ThreadPoolExecutor(4) as ex: R = [x for x in ex.map(run, rows)]
km = [r["km"] for r in R]
agg = dict(n=len(R), arrival_utc=R[0]["arrival_utc"], median_km=round(st.median(km)), mean_km=round(st.mean(km)),
           farthest=max(R, key=lambda r: r["km"])["name"], farthest_km=round(max(km)),
           shortest=min(R, key=lambda r: r["km"])["name"], shortest_km=round(min(km)),
           most_countries=max(R, key=lambda r: len(r["countries"]))["name"], most_countries_n=max(len(r["countries"]) for r in R),
           crossed_sea_pct=round(100 * sum(1 for r in R if r["seas"]) / len(R)),
           rained_on_pct=round(100 * sum(1 for r in R if r["rain_hours"]) / len(R)),
           biggest_temp_swing=max(R, key=lambda r: r["tmax"] - r["tmin"])["name"], biggest_temp_swing_c=round(max(r["tmax"] - r["tmin"] for r in R)),
           median_companion_spread_km=round(st.median(r["companions_spread_km"] for r in R)))
json.dump(dict(aggregate=agg, journeys=R), open("out/stats.json", "w"), indent=1)
with open("out/stats.md", "w") as f:
    f.write(f"# Live run — air arriving {agg['arrival_utc']}\n\n")
    for k, v in agg.items(): f.write(f"- **{k}**: {v}\n")
    f.write("\n| place | km | countries | first region | seas | stops |\n|---|---|---|---|---|---|\n")
    for r in sorted(R, key=lambda r: -r["km"]):
        f.write(f"| {r['name']} | {round(r['km']):,} | {', '.join(r['countries'])} | {r['start']['region'] or ''} | {', '.join(r['seas'])} | {' → '.join(r['stops'][:6])} |\n")
print(json.dumps(agg, indent=1))
