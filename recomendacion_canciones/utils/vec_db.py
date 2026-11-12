import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

INDEX_NAME = "chichazam-recomendacion-mert"
NAMESPACE = "mert-10s-5s"  # versionar si cambia el chunking o el modelo
DIMENSION = 768
METRIC = "cosine"
UPSERT_BATCH = 200
QUERY_CHUNKS = 300  # maximo de chunks por query


def get_index():
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    if not pc.has_index(INDEX_NAME):
        pc.create_index(INDEX_NAME, dimension=DIMENSION, metric=METRIC,
                        spec=ServerlessSpec(cloud="aws", region="us-east-1"))
        while not pc.describe_index(INDEX_NAME).status.ready:
            time.sleep(2)
    return pc.Index(INDEX_NAME)


def upsert_chunks(index, vectors, metadata) -> int:
    for i in range(0, len(vectors), UPSERT_BATCH):
        index.upsert(
            vectors=[{"id": m["chunk_id"], "values": v.tolist(), "metadata": m}
                     for v, m in zip(vectors[i:i + UPSERT_BATCH], metadata[i:i + UPSERT_BATCH])],
            namespace=NAMESPACE,
        )
    return len(vectors)


def aggregate_songs(matches, top_k: int | None = None) -> list[dict]: #  Chunks -> canciones, quedandose con la similitud maxima de cada cancion
    best: dict[str, dict] = {}
    for m in matches:
        md = m.metadata
        if md["song_id"] not in best or m.score > best[md["song_id"]]["score"]:
            best[md["song_id"]] = {
                "song_id": md["song_id"], "name": md["title"], "genre": md["genre"],
                "source_url": md["source_url"], "score": float(m.score),
                "start_sec": md["start_sec"],
            }
    ranked = sorted(best.values(), key=lambda r: -r["score"])
    return ranked if top_k is None else ranked[:top_k]


def find_song(index, vector, title: str) -> dict | None: # -> metadata de una cncion, hallando por titulo
    res = index.query(vector=vector.tolist(), top_k=1, namespace=NAMESPACE,
                      filter={"title": {"$eq": title}}, include_metadata=True)
    return dict(res.matches[0].metadata) if res.matches else None


def search_songs(index, query_vectors, top_k: int = 5,
                 exclude_songs=(), exclude_chunks=(), genre: str | None = None) -> list[dict]:
    cond = {}
    if exclude_songs:
        cond["song_id"] = {"$nin": list(exclude_songs)}
    if exclude_chunks:
        cond["chunk_id"] = {"$nin": list(exclude_chunks)}
    if genre:
        cond["genre"] = {"$eq": genre}

    best: dict[str, dict] = {}
    for vector in query_vectors:
        res = index.query(vector=vector.tolist(), top_k=QUERY_CHUNKS, namespace=NAMESPACE,
                          filter=cond or None, include_metadata=True)
        for song in aggregate_songs(res.matches):
            if song["song_id"] not in best or song["score"] > best[song["song_id"]]["score"]:
                best[song["song_id"]] = song
                
    return sorted(best.values(), key=lambda r: -r["score"])[:top_k]
