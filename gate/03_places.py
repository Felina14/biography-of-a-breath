"""Gate step 3: find real named places along the journey from Overture Maps
(divisions theme, AWS Open Data, s3://overturemaps-us-west-2) with DuckDB.
Usage: python gate/03_places.py out/journey_Delhi_10.json"""
import json, math, sys
import duckdb

CORRIDOR_KM = 25
J = json.load(open(sys.argv[1])); pts = J["points"]
lats = [p["lat"] for p in pts]; lons = [p["lon"] for p in pts]
pad = 0.5
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET s3_access_key_id=''; SET s3_secret_access_key='';")
rels = con.execute("SELECT DISTINCT regexp_extract(file, 'release/([^/]+)/', 1) r FROM glob('s3://overturemaps-us-west-2/release/*/theme=divisions/type=division/*') ORDER BY r DESC").fetchall()
rel = rels[0][0]; print("Overture release:", rel)
rows = con.execute(f"""
  SELECT names.primary AS name, region, country, population,
         (bbox.xmin + bbox.xmax)/2 AS lon, (bbox.ymin + bbox.ymax)/2 AS lat
  FROM read_parquet('s3://overturemaps-us-west-2/release/{rel}/theme=divisions/type=division/*', hive_partitioning=1)
  WHERE subtype = 'locality'
    AND bbox.xmin BETWEEN {min(lons)-pad} AND {max(lons)+pad}
    AND bbox.ymin BETWEEN {min(lats)-pad} AND {max(lats)+pad}
    AND (population IS NULL OR population >= 20000)
""").fetchall()
print(len(rows), "candidate towns/cities in the journey's bounding box")

def km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1]-a[1])
    x = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371*math.asin(math.sqrt(x))

stops = []
for name, region, cc, pop, lo, la in rows:
    d, p = min((km((la, lo), (q["lat"], q["lon"])), q) for q in pts)
    if d <= CORRIDOR_KM:
        stops.append(dict(name=name, region=region, country=cc, population=pop, lat=la, lon=lo, dist_km=round(d, 1),
                          hours_ago=p["hours_ago"], temp_c=p["temp_c"], rh=p["rh"], rain_mmh=p["rain_mmh"]))
import re
SKIP = re.compile(r"(stadtbezirk|bezirk|innenstadt|metropolitan|district|ward|zone|arrondissement|sector|borough of)", re.I)
seen, clean = set(), []
for s in sorted(stops, key=lambda s: -(s["population"] or 0)):
    key = s["name"].lower()
    if SKIP.search(s["name"]) or key in seen: continue
    seen.add(key); clean.append(s)
# journey stops: big places first, but keep them spread out along the path (>= 60 km apart)
chosen = []
for s in clean:
    if all(km((s["lat"], s["lon"]), (c["lat"], c["lon"])) >= 60 for c in chosen):
        chosen.append(s)
    if len(chosen) >= 12: break
chosen.sort(key=lambda s: -s["hours_ago"])
J["places"] = chosen
J["places_all"] = sorted(clean, key=lambda s: -s["hours_ago"])
J["passport"] = dict(countries=sorted({s["country"] for s in clean if s["country"]}),
                     towns_20k_plus=sum(1 for s in clean if (s["population"] or 0) >= 20000),
                     smaller_places=sum(1 for s in clean if not s["population"]),
                     people_in_named_towns=sum(s["population"] or 0 for s in clean))
stops = chosen
json.dump(J, open(sys.argv[1], "w"), indent=1)
print(f"{len(clean)} places within {CORRIDOR_KM} km of the path; {len(stops)} journey stops. Passport:", J["passport"])
for s in stops:
    pop = f"{s['population']:,}" if s["population"] else "pop n/a"
    print(f"  -{s['hours_ago']:>5.0f} h  {s['name']} ({s['region'] or s['country']}, {pop})  {s['dist_km']} km off path, {s['temp_c']} C, rain {s['rain_mmh']} mm/h")
