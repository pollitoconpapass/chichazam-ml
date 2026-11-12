import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.embeddings import center, embed, save_mean
from utils.vec_db import INDEX_NAME, NAMESPACE, get_index, upsert_chunks
from utils.audio_handling import chunks, download_dataset, load_audio, load_catalog

parser = argparse.ArgumentParser(description="Vectoriza el dataset y lo sube a Pinecone.")
parser.add_argument("--limit", type=int, default=None, help="procesar solo las primeras N canciones")
args = parser.parse_args()

dataset_dir = download_dataset()
canciones = load_catalog(dataset_dir)
if args.limit:
    canciones = canciones[:args.limit]

print(f"Indexando {len(canciones)} canciones -> {INDEX_NAME}/{NAMESPACE}")
index = get_index()
todos_vectores, toda_metadata = [], []

for i, cancion in enumerate(canciones, 1):
    audio_path = dataset_dir / "audio" / cancion["filename"]
    if not audio_path.exists():
        print(f"[{i}/{len(canciones)}] {cancion['name']}: archivo no encontrado")
        continue

    trozos = chunks(load_audio(audio_path))
    todos_vectores.append(embed([audio for audio, _ in trozos]))
    toda_metadata += [
        {
            "chunk_id": f'{cancion["id"]}|{start}',
            "song_id": cancion["id"],
            "title": cancion["name"],
            "genre": cancion.get("genre") or "",
            "source_url": cancion.get("source_url") or "",
            "start_sec": start,
            "duration_seconds": cancion.get("duration_seconds") or 0,
        }
        for _, start in trozos
    ]
    print(f"[{i}/{len(canciones)}] {cancion['name']}: {len(trozos)} chunks")

# El centrado necesita la media de todo el corpus, por eso se sube al final.
vectores = np.concatenate(todos_vectores)
vectores = center(vectores, save_mean(vectores))
upsert_chunks(index, vectores, toda_metadata)

print(f"\nListo: {len(canciones)} canciones, {len(vectores)} chunks")
stats = index.describe_index_stats()
print("Vectores en el namespace:", stats.namespaces.get(NAMESPACE))
