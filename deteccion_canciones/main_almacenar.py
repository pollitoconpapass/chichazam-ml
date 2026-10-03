import json
from pathlib import Path
from collections import Counter
from utils.hashing import hashes
from utils.patterns import peaks
from utils.spectrogram import generate_spectrogram
from huggingface_hub import snapshot_download
from utils.fingerprint_db import fast_ingest, get_connection, song_exists, store_song

DATASET_ID = "pollitoconpapass/dataset-peru-shazam"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"

# === Helpers para el dataset de audios de Hugging Face ===
def download_dataset() -> Path:
    return Path(snapshot_download(repo_id=DATASET_ID, repo_type="dataset"))

def load_catalog(dataset_dir: Path) -> list[dict]:
    catalog = json.loads((dataset_dir / "catalog.json").read_text(encoding="utf-8"))
    validos = [e for e in catalog.values() if e.get("status") == "downloaded" and not e.get("error")]
    repeticiones = Counter(e["title"] for e in validos)
    for entry in validos:
        entry["name"] = entry["title"] if repeticiones[entry["title"]] == 1 else f'{entry["title"]} ({entry["id"]})'
    return validos


# === MAIN ===
dataset_dir = download_dataset()
canciones = load_catalog(dataset_dir)
conn = get_connection(str(DB_PATH))

insertadas, omitidas, fallidas = 0, 0, 0
print(f"Canciones a procesar: {len(canciones)}")

with fast_ingest(conn):
    for i, cancion in enumerate(canciones, 1):
        # Verificaciones previas
        name = cancion["name"]

        if song_exists(conn, name):
            omitidas += 1
            continue

        # Procesamiento del audio
        audio_path = dataset_dir / "audio" / cancion["filename"]
        if not audio_path.exists():
            fallidas += 1
            print(f"[{i}/{len(canciones)}] {name}: archivo no encontrado ({cancion['filename']})")
            continue

        try:
            # NUCLEO DE TODO TODO TODITO
            h = hashes(peaks(generate_spectrogram(str(audio_path)))) # -> generacion de hashes
            song_id = store_song(conn, name, h) # -> guardar en la bd
        except Exception as exc:
            fallidas += 1
            print(f"[{i}/{len(canciones)}] {name}: error al procesar ({exc})")
            continue

        insertadas += 1
        print(f"[{i}/{len(canciones)}] {name}: {len(h)} hashes -> song_id={song_id}")

# Stats (solo pa mostrar)
total_canciones, total_hashes = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(n_hashes), 0) FROM songs"
).fetchone()
conn.close()

print("\n\n--- Ingesta finalizada ---")
print(f"Insertadas: {insertadas} | Omitidas (ya existentes): {omitidas} | Fallidas: {fallidas}")
print(f"En la base de datos: {total_canciones} canciones, {total_hashes} hashes ({DB_PATH})")
