"""Build ref/places.npz: every Overture Maps locality with population >= 15,000 worldwide
(names, region, country, population, lat/lon). Run where S3 is reachable (DuckDB httpfs)."""
import sys, duckdb, numpy as np
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET s3_access_key_id=''; SET s3_secret_access_key=''; SET http_timeout=300; SET http_retries=8;")
rel = con.execute("SELECT max(regexp_extract(file, 'release/([^/]+)/', 1)) FROM glob('s3://overturemaps-us-west-2/release/*/theme=divisions/type=division/*')").fetchone()[0]
rows = con.execute(f"""SELECT coalesce(names.common['en'], names.primary), coalesce(region,''), coalesce(country,''), population,
    (bbox.xmin+bbox.xmax)/2, (bbox.ymin+bbox.ymax)/2
  FROM read_parquet('s3://overturemaps-us-west-2/release/{rel}/theme=divisions/type=division/*', hive_partitioning=1)
  WHERE subtype='locality' AND population >= 15000 AND names.primary IS NOT NULL""").fetchall()
n, r, c, p, lo, la = zip(*rows)
np.savez_compressed(sys.argv[1] if len(sys.argv) > 1 else "ref/places.npz", name=np.array(n), region=np.array(r), country=np.array(c),
                    pop=np.array(p, dtype=np.int64), lon=np.array(lo, dtype=np.float32), lat=np.array(la, dtype=np.float32), release=np.array(rel))
print("Overture", rel, "localities >= 15k:", len(rows))
