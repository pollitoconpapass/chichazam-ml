import sys
import random
import argparse
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.vec_db import NAMESPACE, QUERY_CHUNKS, aggregate_songs, get_index

FETCH_BATCH = 500

def sample_chunks(index, por_cancion: int, seed: int) -> list[str]:
    random.seed(seed)
    ids_por_cancion = defaultdict(list)
    for page in index.list(namespace=NAMESPACE):
        for chunk_id in page:
            ids_por_cancion[chunk_id.split("|")[0]].append(chunk_id)
    return [cid for ids in ids_por_cancion.values() for cid in random.sample(ids, min(por_cancion, len(ids)))]


def main(por_cancion: int, seed: int):
    index = get_index()
    ids = sample_chunks(index, por_cancion, seed)

    vectores = {}
    for i in range(0, len(ids), FETCH_BATCH):
        vectores.update(index.fetch(ids=ids[i:i + FETCH_BATCH], namespace=NAMESPACE).vectors)

    identidad, mismos_scores, precision = [], [], []
    generos = Counter()

    for i, (chunk_id, vector) in enumerate(vectores.items(), 1):
        md = vector.metadata
        cancion, genero = md["song_id"], md["genre"]
        generos[genero] += 1

        # Identidad: se excluye solo el chunk consultado, no su cancion.
        res = index.query(vector=vector.values, top_k=QUERY_CHUNKS, namespace=NAMESPACE,
                          filter={"chunk_id": {"$ne": chunk_id}}, include_metadata=True)
        ranking = aggregate_songs(res.matches)
        identidad.append(bool(ranking) and ranking[0]["song_id"] == cancion)
        mismos_scores.append(next((r["score"] for r in ranking if r["song_id"] == cancion), 0.0))

        # Calidad de recomendacion: se excluye la cancion completa.
        res = index.query(vector=vector.values, top_k=QUERY_CHUNKS, namespace=NAMESPACE,
                          filter={"song_id": {"$ne": cancion}}, include_metadata=True)
        recs = aggregate_songs(res.matches, top_k=5)
        precision.append(sum(r["genre"] == genero for r in recs) / len(recs))

        if i % 50 == 0:
            print(f"  {i}/{len(vectores)} consultas...")

    total = len(vectores)
    print(f"\nMuestras: {total} chunks")
    print(f"Identidad top-1 (excluyendo el mismo chunk): {100 * sum(identidad) / len(identidad):.1f}%")
    umbral = np.percentile([s for s, ok in zip(mismos_scores, identidad) if ok], 5)
    print(f"Score misma cancion: p5={umbral:.3f} p50={np.percentile(mismos_scores, 50):.3f}")

    por_genero = defaultdict(list)
    for p, (chunk_id, vector) in zip(precision, vectores.items()):
        por_genero[vector.metadata["genre"]].append(p)

    print("\nPrecision@5 por genero (baseline aleatorio):")
    for genero, valores in sorted(por_genero.items()):
        print(f"  {genero:<18} {np.mean(valores):.3f}  ({generos[genero] / total:.3f})")
    print(f"  {'promedio':<18} {np.mean(precision):.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evalua la recomendacion por genero y calibra el umbral.")
    parser.add_argument("--por-cancion", type=int, default=2, help="chunks consultados por cancion")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    main(args.por_cancion, args.seed)
