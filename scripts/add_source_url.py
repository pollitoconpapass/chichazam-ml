import sys
import json
import sqlite3
import argparse
import collections
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"
CATALOG_PATH = PROJECT_ROOT / "deteccion_canciones" / "catalog.json"


def load_name_to_url(catalog_path: Path) -> dict[str, str]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validos = [e for e in catalog.values() if e.get("status") == "downloaded" and not e.get("error")]
    repeticiones = collections.Counter(e["title"] for e in validos)
    mapping = {}
    for entry in validos:
        name = entry["title"] if repeticiones[entry["title"]] == 1 else f'{entry["title"]} ({entry["id"]})'
        mapping[name] = entry["source_url"]
    return mapping


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="solo muestra lo que haria, no modifica la db")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    args = parser.parse_args()

    name_to_url = load_name_to_url(args.catalog)
    unmatched: list[str] = []
    conn = sqlite3.connect(args.db)
    try:
        has_url = has_column(conn, "songs", "source_url")
        if not has_url:
            if args.dry_run:
                print("[dry-run] ALTER TABLE songs ADD COLUMN source_url TEXT")
            else:
                conn.execute("ALTER TABLE songs ADD COLUMN source_url TEXT")
                has_url = True
                print("Columna source_url agregada a songs")
        else:
            print("La columna source_url ya existe")

        if has_url:
            rows = conn.execute("SELECT id, name, source_url FROM songs").fetchall()
        else:  # dry-run sin columna: no hay URL previa
            rows = [(song_id, name, None) for song_id, name in
                    conn.execute("SELECT id, name FROM songs").fetchall()]

        updates, unmatched = [], []
        for song_id, name, current in rows:
            url = name_to_url.get(name)
            if url is None:
                unmatched.append(name)
            elif url != current:
                updates.append((url, song_id))

        if updates:
            if args.dry_run:
                print(f"[dry-run] se actualizarian {len(updates)} filas:")
                for song_id in [u[1] for u in updates[:10]]:
                    name = next(n for i, n, _ in rows if i == song_id)
                    print(f"  {song_id}: {name}")
                if len(updates) > 10:
                    print(f"  ... y {len(updates) - 10} mas")
            else:
                conn.executemany("UPDATE songs SET source_url = ? WHERE id = ?", updates)
                conn.commit()
                print(f"Actualizadas {len(updates)} filas")
        else:
            print("Nada que actualizar")

        if unmatched:
            print(f"ADVERTENCIA: {len(unmatched)} canciones sin URL en el catalogo:")
            for name in unmatched:
                print(f"  - {name}")

        if has_url:
            total, con_url = conn.execute(
                "SELECT COUNT(*), COUNT(source_url) FROM songs"
            ).fetchone()
        else:
            total, con_url = len(rows), 0
        print(f"\nResultado: {con_url}/{total} canciones con source_url")
    finally:
        conn.close()

    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
