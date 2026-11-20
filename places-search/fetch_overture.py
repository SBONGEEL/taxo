"""Fetches Overture Maps places (JO/DZ/LY) and buildings (the eight measured cities) with DuckDB, anonymous S3. Runs OFF production.

usage: python -I fetch_overture.py <workdir> [release]
  writes <workdir>/overture_places.parquet   (cc, name, name_ar, name_en, cat, confidence, lat, lng, locality, street)
         <workdir>/buildings.geojsonl         (Overture Buildings — OSM + Microsoft + Google Open Buildings, conflated by Overture; ODbL)
         <workdir>/overture_release.txt

**بلا إصدارٍ مكتوبٍ يُؤخذ أحدثُ ما في الحاوية** — فالتحديثُ الشهريُّ لا يحتاج يداً تبدّل رقماً.
"""
import json
import os
import sys

import duckdb

WORK = sys.argv[1]
BUCKET = "s3://overturemaps-us-west-2/release"
COUNTRY_BOX = {"JO": (34.9, 29.1, 39.4, 33.4), "DZ": (-8.7, 18.9, 12.0, 37.1), "LY": (9.3, 19.5, 25.2, 33.2)}
CITY_BOXES = [(35.75, 31.85, 36.05, 32.10), (35.76, 31.69, 35.83, 31.74), (35.80, 32.50, 35.90, 32.59),
              (2.90, 36.65, 3.25, 36.82), (-0.75, 35.62, -0.52, 35.78), (13.05, 32.75, 13.40, 32.92),
              (19.95, 32.02, 20.20, 32.20), (15.00, 32.30, 15.15, 32.42)]

con = duckdb.connect()
for ext in ("httpfs", "spatial"):
    con.execute(f"INSTALL {ext}; LOAD {ext};")
con.execute("SET s3_region='us-west-2'; SET s3_access_key_id=''; SET s3_secret_access_key=''; SET s3_session_token='';")


def latest() -> str:
    rows = con.execute(f"SELECT DISTINCT split_part(file, '/', 5) AS r FROM glob('{BUCKET}/*/theme=places/type=place/*') ORDER BY r DESC").fetchall()
    return rows[0][0]


release = sys.argv[2] if len(sys.argv) > 2 else latest()
print("overture release", release, flush=True)
with open(os.path.join(WORK, "overture_release.txt"), "w") as f:
    f.write(release)


def common(m, key):
    """`names.common` خريطةٌ يعيدها DuckDB قاموساً أو {key: [...], value: [...]} بحسب الإصدار — تُقرأ بالشكلين."""
    if not m:
        return None
    if isinstance(m, dict) and "key" in m and "value" in m and isinstance(m["key"], list):
        return dict(zip(m["key"], m["value"])).get(key)
    return m.get(key) if isinstance(m, dict) else None


rows = []
for cc, (x0, y0, x1, y1) in COUNTRY_BOX.items():
    src = f"read_parquet('{BUCKET}/{release}/theme=places/type=place/*', hive_partitioning=1)"
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src} LIMIT 0").fetchall()}
    cat = "categories.primary" if "categories" in cols else "basic_category"
    # **المعرِّفُ والعلامة** (SPEC §١٠٩-ب): `id` مفتاحٌ ثابتٌ لاسم اللوحة، و`brand` تُبقي اسمَ العلامة كما تكتبه
    brand = "brand.wikidata, brand.names.primary" if "brand" in cols else "NULL, NULL"
    q = f"""
      SELECT names.primary, names.common, {cat}, confidence, (bbox.ymin + bbox.ymax) / 2, (bbox.xmin + bbox.xmax) / 2,
             addresses[1].locality, addresses[1].freeform, id, {brand}
      FROM {src}
      WHERE bbox.xmin BETWEEN {x0} AND {x1} AND bbox.ymin BETWEEN {y0} AND {y1} AND addresses[1].country = '{cc}'
    """
    got = con.execute(q).fetchall()
    for name, names_common, category, conf, lat, lng, locality, street, oid, brand_wd, brand_name in got:
        if not name:
            continue
        rows.append((cc, name, common(names_common, "ar"), common(names_common, "en"), category, conf or 0.0, lat, lng, locality, street,
                     oid, brand_wd, brand_name, common(names_common, "fr")))
    print(cc, "places", len(got), flush=True)

con.execute("CREATE TABLE ov(cc VARCHAR, name VARCHAR, name_ar VARCHAR, name_en VARCHAR, cat VARCHAR, confidence DOUBLE, lat DOUBLE, lng DOUBLE, locality VARCHAR, street VARCHAR, oid VARCHAR, brand_wd VARCHAR, brand_name VARCHAR, name_fr VARCHAR)")
con.executemany("INSERT INTO ov VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
con.execute(f"COPY ov TO '{os.path.join(WORK, 'overture_places.parquet')}' (FORMAT PARQUET)")

n = 0
with open(os.path.join(WORK, "buildings.geojsonl"), "w", encoding="utf-8") as out:
    for x0, y0, x1, y1 in CITY_BOXES:
        q = f"""
          SELECT ST_AsGeoJSON(geometry) FROM read_parquet('{BUCKET}/{release}/theme=buildings/type=building/*', hive_partitioning=1)
          WHERE bbox.xmin BETWEEN {x0} AND {x1} AND bbox.ymin BETWEEN {y0} AND {y1}
        """
        for (geometry,) in con.execute(q).fetchall():
            out.write(json.dumps({"type": "Feature", "properties": {},
                                  "geometry": json.loads(geometry)}) + "\n")
            n += 1
        print("buildings so far", n, flush=True)
