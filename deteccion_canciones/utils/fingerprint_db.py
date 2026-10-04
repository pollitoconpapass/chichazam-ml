import sqlite3
from collections import defaultdict
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    n_hashes   INTEGER NOT NULL DEFAULT 0,
    source_url TEXT
);
 
CREATE TABLE IF NOT EXISTS fingerprints (
    hash         INTEGER NOT NULL,   -- entero de 32 bits (cabe en el INTEGER de 64 bits de SQLite)
    song_id      INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    anchor_time  INTEGER NOT NULL,   -- frame del punto ancla
    PRIMARY KEY (hash, song_id, anchor_time)
) WITHOUT ROWID;
 
CREATE INDEX IF NOT EXISTS idx_fp_song ON fingerprints(song_id);
"""

# === CONEXIONES Y UTILIDADES ===
def get_connection(db_path: str = "fingerprints.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)")}
    if "source_url" not in cols:
        conn.execute("ALTER TABLE songs ADD COLUMN source_url TEXT")
    return conn

@contextmanager
def fast_ingest(conn: sqlite3.Connection):
    conn.execute("PRAGMA synchronous = OFF;")
    try:
        yield
    finally:
        conn.execute("PRAGMA synchronous = NORMAL;")


# === MANEJO de CANCIONES ===
def song_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM songs WHERE name = ?", (name,)).fetchone() is not None

def delete_song(conn: sqlite3.Connection, name: str) -> None:
    # ON DELETE CASCADE borra también sus fingerprints
    with conn:
        conn.execute("DELETE FROM songs WHERE name = ?", (name,))

def store_song(conn: sqlite3.Connection, name: str, hashes: list[tuple[int, int]],
               replace: bool = False, source_url: str | None = None) -> int | None:
    if song_exists(conn, name):
        if not replace:
            return None
        delete_song(conn, name)
 
    with conn:  # una sola transacción: o se guarda todo o nada
        cur = conn.execute("INSERT INTO songs(name, source_url) VALUES (?, ?)", (name, source_url))
        song_id = cur.lastrowid
        conn.executemany(
            # OR IGNORE: el mismo (hash, song, tiempo) puede repetirse y la PK lo rechazaría
            "INSERT OR IGNORE INTO fingerprints(hash, song_id, anchor_time) VALUES (?, ?, ?)",
            ((int(h), song_id, int(t)) for h, t in hashes),
        )
        n = conn.execute(
            "SELECT COUNT(*) FROM fingerprints WHERE song_id = ?", (song_id,)
        ).fetchone()[0]
        conn.execute("UPDATE songs SET n_hashes = ? WHERE id = ?", (n, song_id))
    return song_id


# === FUNCIONES RETRIEVAL ===
def find_matches(conn: sqlite3.Connection, query_hashes: list[tuple[int, int]],
                 max_hash_freq: int | None = None) -> list[tuple[int, int, int]]:

    conn.execute("CREATE TEMP TABLE IF NOT EXISTS query_hashes (hash INTEGER, t INTEGER)")
    conn.execute("DELETE FROM query_hashes")
    conn.executemany(
        "INSERT INTO query_hashes(hash, t) VALUES (?, ?)",
        ((int(h), int(t)) for h, t in query_hashes),
    )
 
    if max_hash_freq is None:
        sql = """
            SELECT f.song_id, f.anchor_time - q.t AS delta, COUNT(*) AS votes
            FROM query_hashes q
            JOIN fingerprints f ON f.hash = q.hash
            GROUP BY f.song_id, delta
        """
        rows = conn.execute(sql).fetchall()
    else:
        sql = """
            WITH common AS (
                SELECT f.hash FROM fingerprints f
                JOIN (SELECT DISTINCT hash FROM query_hashes) qd ON qd.hash = f.hash
                GROUP BY f.hash HAVING COUNT(*) > ?
            )
            SELECT f.song_id, f.anchor_time - q.t AS delta, COUNT(*) AS votes
            FROM query_hashes q
            JOIN fingerprints f ON f.hash = q.hash
            WHERE q.hash NOT IN (SELECT hash FROM common)
            GROUP BY f.song_id, delta
        """
        rows = conn.execute(sql, (max_hash_freq,)).fetchall()
 
    conn.execute("DELETE FROM query_hashes")
    return rows

def score_matches(rows: list[tuple[int, int, int]], tolerance: int = 1) -> dict[int, tuple[int, int]]:
    by_song: dict[int, dict[int, int]] = defaultdict(dict)
    for song_id, delta, votes in rows:
        by_song[song_id][delta] = votes
 
    scores = {}
    for song_id, deltas in by_song.items():
        best_score, best_delta = 0, 0
        for d in deltas:
            s = sum(deltas.get(d + k, 0) for k in range(-tolerance, tolerance + 1))
            if s > best_score:
                best_score, best_delta = s, d
        scores[song_id] = (best_score, best_delta)
    return scores

def identify(conn: sqlite3.Connection, query_hashes: list[tuple[int, int]],
             top_k: int = 5, min_score: int = 5, tolerance: int = 1,
             max_hash_freq: int | None = None) -> list[dict]:
    
    rows = find_matches(conn, query_hashes, max_hash_freq)
    scores = score_matches(rows, tolerance)
 
    ranked = sorted(
        ((sid, sc, d) for sid, (sc, d) in scores.items() if sc >= min_score),
        key=lambda x: -x[1],
    )[:top_k]
    if not ranked:
        return []
 
    meta = {row[0]: row[1:] for row in conn.execute(
        f"SELECT id, name, source_url FROM songs WHERE id IN ({','.join('?' * len(ranked))})",
        [sid for sid, _, _ in ranked],
    )}
 
    return [
        {"song_id": sid, "name": meta[sid][0], "source_url": meta[sid][1], "score": sc,
         "offset_frames": d}  # d * HOP / SR = segundos en que empieza la grabación dentro de la canción
        for sid, sc, d in ranked
    ]