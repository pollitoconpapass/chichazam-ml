# Este script añade canciones nuevas a la base de datos de reconocimiento y al dataset de Hugging Face.
# Flujo: buscar la cancion con yt-dlp -> descargar el audio -> generar hashes -> guardar en la BD -> subir a Hugging Face.
# Consideraciones: se verifica por separado si la cancion ya esta en la BD (por source_url) y en HF (por id de YouTube
# en catalog.json / audio/<id>.wav). Si ya existe en ambos se omite; si falta en uno, se ingresa solo ahi.
import os
import sys
import json
import yt_dlp
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import HfHubHTTPError
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from recoleccion_datos.config.config_ytdlp import BASE_YDL_OPTS
from deteccion_canciones.utils.hashing import hashes
from deteccion_canciones.utils.patterns import peaks
from deteccion_canciones.utils.spectrogram import generate_spectrogram
from deteccion_canciones.utils.fingerprint_db import fast_ingest, get_connection, store_song

DB_PATH = PROJECT_ROOT / "fingerprints.db"

# ==== Config de Hugging Face ====
HF_REPO_ID = "pollitoconpapass/dataset-peru-shazam"
REPO_TYPE = "dataset"
AUDIO_DIR_IN_REPO = "audio"  # los wavs viven en audio/<id>.wav dentro del repo
CATALOG_NAME = "catalog.json"

load_dotenv(PROJECT_ROOT / ".env")
HF_TOKEN = os.getenv("HF_TOKEN")
api = HfApi(token=HF_TOKEN) if HF_TOKEN else None

# ==== AGREGAR AQUI LAS CANCIONES A AGREGAR (cambia estas canciones cuando quieras ctm) ===
CANCIONES = [
    {"url": "https://www.youtube.com/watch?v=eIqE5bGv6hw", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=X2Z6ybm1GsU", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=8_jGspz29-w", "genre": "huayno"},
    {"url": "https://www.youtube.com/watch?v=TKoWxpnsqKk", "genre": "huayno"}
]
# ==========================================================================================


# === Descargar audio usando yt-dlp ===
def download_audio(url: str, out_dir: Path) -> tuple[Path, dict]:
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
        candidates = sorted(out_dir.glob(f"{info.get('id', '')}.wav")) # -> buscar por el id del video
        if not candidates:
            raise FileNotFoundError(f"No se generó archivo wav para {url}")
        audio_path = candidates[0]
    return audio_path, info


# ==== UTILS BD ====
def song_exists_in_db(conn, source_url: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM songs WHERE source_url = ?", (source_url,)
    ).fetchone() is not None


# ==== UTILS HUGGING FACE ====
def load_hf_catalog() -> dict:
    if api is None:
        return {}
    try:
        catalog_path = hf_hub_download(
            repo_id=HF_REPO_ID, filename=CATALOG_NAME, repo_type=REPO_TYPE, token=HF_TOKEN
        )
        with open(catalog_path) as f:
            return json.load(f)
    except HfHubHTTPError:
        return {}

def load_hf_audio_files() -> set[str]:
    if api is None:
        return set()
    files = api.list_repo_files(HF_REPO_ID, repo_type=REPO_TYPE)
    return {
        Path(f).stem for f in files
        if f.startswith(f"{AUDIO_DIR_IN_REPO}/") and f.endswith(".wav")
    }

def upload_songs_to_hf(pending: list[dict], catalog: dict) -> None: # -> sube los audos pendientes y el catalog.json actualizado en un solo commit.
    with tempfile.TemporaryDirectory(prefix="hf_upload_") as tmp:
        tmp_dir = Path(tmp)
        audio_dir = tmp_dir / AUDIO_DIR_IN_REPO
        audio_dir.mkdir()

        # symlinks para no copiar los wavs pesados
        for item in pending:
            os.symlink(item["audio_path"], audio_dir / item["filename"])

        catalog_path = tmp_dir / CATALOG_NAME
        with open(catalog_path, "w") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        print(f"\nSubiendo {len(pending)} audio(s) + {CATALOG_NAME} a {HF_REPO_ID} (un solo commit)...")
        api.upload_folder(
            folder_path=str(tmp_dir),
            repo_id=HF_REPO_ID,
            repo_type=REPO_TYPE,
            token=HF_TOKEN,
            commit_message=f"Add {len(pending)} song(s): {', '.join(i['id'] for i in pending)}",
        )

# === FUNCION PRINCIPAL ===
def main() -> None:
    conn = get_connection(str(DB_PATH))

    insertadas_bd, insertadas_hf, omitidas, fallidas = 0, 0, 0, 0

    if api is None:
        print("ADVERTENCIA: no se encontró HF_TOKEN en .env -> solo se ingresará a la BD.")
    catalog = load_hf_catalog()
    hf_audio_ids = load_hf_audio_files()

    print(f"Canciones a procesar: {len(CANCIONES)}")
    print(f"En HF: {len(catalog)} entradas en catalog, {len(hf_audio_ids)} audios\n")

    pending_upload: list[dict] = []  # cosas a subir a HF al final

    with tempfile.TemporaryDirectory(prefix="add_song_") as tmp:
        tmp_dir = Path(tmp)
        with fast_ingest(conn):
            for i, cancion in enumerate(CANCIONES, 1):
                url = cancion["url"]
                genre = cancion.get("genre")

                try:
                    audio_path, info = download_audio(url, tmp_dir)
                    name = info.get("title") or info.get("id") or url
                    video_id = info.get("id")
                    duration = int(info.get("duration") or 0)
                except Exception as exc:
                    fallidas += 1
                    print(f"[{i}/{len(CANCIONES)}] {url}: error al descargar ({exc})")
                    continue

                # Verificacion por destino (bbdd o hf)
                en_bd = song_exists_in_db(conn, url)
                en_hf = video_id in hf_audio_ids or video_id in catalog

                if en_bd and en_hf:
                    omitidas += 1
                    print(f"[{i}/{len(CANCIONES)}] {name}: ya existe en la BD y en HF")
                    continue

                if en_bd and not en_hf:
                    print(f"[{i}/{len(CANCIONES)}] {name}: en la BD pero no en HF -> solo subiendo a HF")
                elif en_hf and not en_bd:
                    print(f"[{i}/{len(CANCIONES)}] {name}: en HF pero no en la BD -> solo ingiriendo a la BD")
                else:
                    print(f"[{i}/{len(CANCIONES)}] {name}: nueva -> ingiriendo a la BD y HF")

                # BBDD
                if not en_bd:
                    try:
                        # NUCLEO DE TODO TODO TODITO
                        h = hashes(peaks(generate_spectrogram(str(audio_path))))  # -> generacion de hashes
                        song_id = store_song(conn, name, h, source_url=url)       # -> guardar en la bd
                        if song_id is None:
                            raise ValueError(f"ya existe una cancion llamada '{name}' con otra URL")
                        insertadas_bd += 1
                        print(f"[{i}/{len(CANCIONES)}] {name}: {len(h)} hashes -> song_id={song_id}")
                    except Exception as exc:
                        fallidas += 1
                        print(f"[{i}/{len(CANCIONES)}] {name}: error al procesar en la BD ({exc})")
                        continue  # si falla la BD, tampoco sube a HF

                # Hugging Face
                if not en_hf:
                    if video_id is None:
                        fallidas += 1
                        print(f"[{i}/{len(CANCIONES)}] {name}: no se pudo obtener el id de YouTube, no se sube a HF")
                        continue
                    now = datetime.now(timezone.utc).isoformat()
                    filename = f"{video_id}.wav"
                    catalog.setdefault(video_id, {
                        "id": video_id,
                        "discovered_at": now,
                    })
                    catalog[video_id].update({
                        "title": name,
                        "duration_seconds": duration,
                        "genre": genre,
                        "filename": filename,
                        "source_url": url,
                        "status": "downloaded",
                        "downloaded_at": now,
                        "error": None,
                    })
                    pending_upload.append({"audio_path": audio_path, "id": video_id, "filename": filename})
                    hf_audio_ids.add(video_id)
                    insertadas_hf += 1

        # Subida final a HF
        if pending_upload and api is not None:
            upload_songs_to_hf(pending_upload, catalog)
        elif pending_upload:
            print("Hay canciones pendientes de subir a HF pero no hay HF_TOKEN.")

    total_canciones, total_hashes = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(n_hashes), 0) FROM songs"
    ).fetchone()
    conn.close()

    # Resumen
    print("\n\n--- Ingesta finalizada ---")
    print(f"Insertadas en la BD: {insertadas_bd} | Insertadas en HF: {insertadas_hf} | "
          f"Omitidas (en ambos): {omitidas} | Fallidas: {fallidas}")
    print(f"En la base de datos: {total_canciones} canciones, {total_hashes} hashes ({DB_PATH})")
    if api is not None:
        print(f"Dataset: https://huggingface.co/datasets/{HF_REPO_ID}")


if __name__ == "__main__":
    main()
