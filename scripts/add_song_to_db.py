# Este script es para añadir una nueva cancion a la base de datos de reconocimiento, aparte de las canciones presentes en el dataset de Hugging Face
# Surgio ya que hubo la necesidad de añadir mas canciones a la base de datos pero sin tener que alterar el proceso original ya existente.
# Flujo: buscar la cancion con yt-dlp -> descargar el audio -> generar hashes -> guardar en la BD.
import sys
import yt_dlp
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "deteccion_canciones"))  # para importar utils.*
sys.path.insert(0, str(PROJECT_ROOT / "recoleccion_datos"))    # para importar config.*

from config.config_ytdlp import BASE_YDL_OPTS
from utils.hashing import hashes
from utils.patterns import peaks
from utils.spectrogram import generate_spectrogram
from utils.fingerprint_db import fast_ingest, get_connection, song_exists, store_song

DB_PATH = PROJECT_ROOT / "fingerprints.db"

# ==== AGREGAR AQUI LAS CANCIONES A AGREGAR (cambia estas canciones cuando quieras ctm) ===
CANCIONES = [
    {"url": "https://www.youtube.com/watch?v=eIqE5bGv6hw", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=X2Z6ybm1GsU", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=8_jGspz29-w", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=TKoWxpnsqKk", "genre": "huayno"}
]
# ==========================================================================================


def download_audio(url: str, out_dir: Path) -> tuple[Path, dict]:
    """Descarga el audio de `url` como wav dentro de `out_dir` y regresa (ruta, info)."""
    opts = {
        **BASE_YDL_OPTS,
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "ignoreerrors": False,  
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,

        # Requerido por YouTube (retos JS): si no, falla con "The page needs to be reloaded"
        "remote_components": {"ejs": "github"},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    audio_path = Path(ydl.prepare_filename(info)).with_suffix(".wav")
    
    if not audio_path.exists(): 
        wavs = sorted(out_dir.glob("*.wav"))
        if not wavs:
            raise FileNotFoundError(f"No se generó archivo wav para {url}")
        audio_path = wavs[0]
    return audio_path, info


def main() -> None:
    conn = get_connection(str(DB_PATH))
    insertadas, omitidas, fallidas = 0, 0, 0
    print(f"Canciones a procesar: {len(CANCIONES)}")

    with tempfile.TemporaryDirectory(prefix="add_song_") as tmp:
        tmp_dir = Path(tmp)
        with fast_ingest(conn):
            for i, cancion in enumerate(CANCIONES, 1):
                url = cancion["url"]

                try:
                    audio_path, info = download_audio(url, tmp_dir)
                    name = info.get("title") or info.get("id") or url
                except Exception as exc:
                    fallidas += 1
                    print(f"[{i}/{len(CANCIONES)}] {url}: error al descargar ({exc})")
                    continue

                if song_exists(conn, name):
                    omitidas += 1
                    print(f"[{i}/{len(CANCIONES)}] {name}: ya existe en la BD")
                    audio_path.unlink(missing_ok=True)
                    continue

                try:
                    # NUCLEO DE TODO TODO TODITO
                    h = hashes(peaks(generate_spectrogram(str(audio_path))))  # -> generacion de hashes
                    song_id = store_song(conn, name, h, source_url=url)       # -> guardar en la bd
                except Exception as exc:
                    fallidas += 1
                    print(f"[{i}/{len(CANCIONES)}] {name}: error al procesar ({exc})")
                    continue
                finally:
                    audio_path.unlink(missing_ok=True)

                insertadas += 1
                print(f"[{i}/{len(CANCIONES)}] {name}: {len(h)} hashes -> song_id={song_id}")

    total_canciones, total_hashes = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(n_hashes), 0) FROM songs"
    ).fetchone()
    conn.close()

    print("\n\n--- Ingesta finalizada ---")
    print(f"Insertadas: {insertadas} | Omitidas (ya existentes): {omitidas} | Fallidas: {fallidas}")
    print(f"En la base de datos: {total_canciones} canciones, {total_hashes} hashes ({DB_PATH})")


if __name__ == "__main__":
    main()
