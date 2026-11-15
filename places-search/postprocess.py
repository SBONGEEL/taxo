"""Rebuilds the FTS table of places.sqlite with a country column and stores normalised names (nalt).

usage: python -I postprocess.py <places.sqlite> <dir holding server.py>
"""
import importlib.util
import os
import sqlite3
import sys
import time

spec = importlib.util.spec_from_file_location("srv", os.path.join(sys.argv[2], "server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)
t = time.time()
db = sqlite3.connect(sys.argv[1])
cols = [r[1] for r in db.execute("PRAGMA table_info(places)")]
if "nalt" not in cols:
    db.execute("ALTER TABLE places ADD COLUMN nalt TEXT")
rows = db.execute("SELECT id, alt FROM places").fetchall()
db.executemany("UPDATE places SET nalt=? WHERE id=?",
               [(" | ".join(dict.fromkeys(srv.norm(n) for n in alt.split(" | "))), i) for i, alt in rows])
db.executescript("DROP TABLE IF EXISTS fts; CREATE VIRTUAL TABLE fts USING fts5(n, c, content='', tokenize='trigram');")
db.execute("INSERT INTO fts(rowid, n, c) SELECT id, replace(nalt, ' | ', ' '), 'qq' || lower(cc) || 'qq' FROM places")
db.execute("INSERT INTO fts(fts) VALUES ('optimize')")
db.commit()
db.execute("VACUUM")
db.close()
print("done", round(time.time() - t), "s", round(os.path.getsize(sys.argv[1]) / 1e6, 1), "MB")
