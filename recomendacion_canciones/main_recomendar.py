import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT_ROOT))

from utils.embeddings import MEAN_PATH, center, embed, load_mean
from utils.audio_handling import chunks, load_audio
from utils.vec_db import find_song, get_index, search_songs
from deteccion_canciones.utils.fingerprint_db import get_connection, identify
from deteccion_canciones.utils.hashing import hashes
from deteccion_canciones.utils.patterns import peaks
from deteccion_canciones.utils.spectrogram import generate_spectrogram

DB_PATH = PROJECT_ROOT / "fingerprints.db"
MIN_SCORE_FINGERPRINT = 20


def detectar_cancion(audio_path: str) -> str | None: # -> funcion de deteccion como en el modulo de deteccion_canciones (va todo de la mano)
    conn = get_connection(str(DB_PATH))
    try:
        query = hashes(peaks(generate_spectrogram(audio_path)))
        res = identify(conn, query, top_k=1, min_score=MIN_SCORE_FINGERPRINT, max_hash_freq=2000)
        return res[0]["name"] if res else None
    finally:
        conn.close()


def recomendar(audio_path: str, top_k: int = 5, cancion_detectada: str | None = None) -> list[dict]:
    if not MEAN_PATH.exists():
        raise SystemExit("Falta embedding_mean.npy; corre main_ingest.py primero.")
    index = get_index()
    vectores = embed([audio for audio, _ in chunks(load_audio(audio_path))])
    vectores = center(vectores, load_mean())

    # Si el clip esta en la base de fingerprints se conoce la cancion exacta:
    # se excluye y se recomienda dentro de su genero.
    detectada = cancion_detectada or detectar_cancion(audio_path) # -> solo para el UI, ya que ahi ya se hace la deteccion de la cancion en otra funcion
    excluir, genero = [], None
    if detectada:
        md = find_song(index, vectores[0], detectada)
        if md:
            excluir, genero = [md["song_id"]], md["genre"]
            print(f'Clip identificado como "{detectada}" [{genero}]; se excluye.')

    return search_songs(index, vectores, top_k=top_k, exclude_songs=excluir, genre=genero)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recomienda canciones parecidas a un clip de audio.")
    parser.add_argument("audio", help="ruta al audio del clip")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    resultados = recomendar(args.audio, args.top_k)
    if not resultados:
        print("Sin recomendaciones.")
    for i, r in enumerate(resultados, 1):
        minuto, segundo = divmod(r["start_sec"], 60)
        print(f'{i}. {r["name"]} [{r["genre"]}] sim={r["score"]:.3f} '
              f'{r["source_url"]} (min {minuto}:{segundo:02d})')
