import os
import sys
import json
import time
import tempfile
import threading
import subprocess
import datetime as dt
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

DEVNULL = open(os.devnull, "w")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"
sys.path.insert(0, str(PROJECT_ROOT))

from deteccion_canciones.utils.hashing import hashes
from deteccion_canciones.utils.patterns import peaks
from deteccion_canciones.utils.spectrogram import generate_spectrogram, SR, HOP
from deteccion_canciones.utils.fingerprint_db import get_connection, identify

MAX_SEGUNDOS = 60 
MIN_SCORE_CONFIABLE = 10
REINTENTOS = 2

FRACASO_TTL = 30
CACHE_DIR = Path("audio_cache")
CACHE_DIR.mkdir(exist_ok=True)
URLS = {}

_locks = {}
_locks_guard = threading.Lock()
_fallos = {}

app = FastAPI()

# === FUNCION PRINCIPAL DETECTAR CANCION ===
def detectar_cancion(audio_file_path: str) -> list:
    conn = get_connection(DB_PATH)
    hashes_query = hashes(peaks(generate_spectrogram(audio_file_path)))
    return identify(conn, hashes_query, top_k=5, min_score=5, max_hash_freq=2000)


# === CONTROL DE VERSIONES ===
def _avisar_si_ytdlp_viejo():
    try:
        v = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()
        anio, mes, dia = (int(x) for x in v.split(".")[:3])
        edad = (dt.date.today() - dt.date(anio, mes, dia)).days
        if edad > 90:
            print(
                f"[AVISO] yt-dlp {v} tiene {edad} dias; YouTube suele devolver "
                f"403 Forbidden con versiones viejas. Actualiza con: pip install -U yt-dlp"
            )
    except Exception as e:
        print(f"[AVISO] no se pudo comprobar la version de yt-dlp: {e}")

_avisar_si_ytdlp_viejo()

# === HELPER FUNCTIONS ===
def _lock(song_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(song_id, threading.Lock())

def url_youtube_en(url: str, segundos: float) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "t"]
    params.append(("t", "%ds" % max(0, int(round(segundos)))))
    return urlunparse(parsed._replace(query=urlencode(params)))

def _limpiar_parciales(song_id: str):
    for f in CACHE_DIR.glob(f"{song_id}.*"):
        if f.suffix != ".wav":
            f.unlink(missing_ok=True)

def asegurar_audio(song_id: str, url: str) -> Path:
    destino = CACHE_DIR / f"{song_id}.wav"
    with _lock(song_id):  # evita descargar dos veces la misma canción
        if destino.exists():
            return destino

        ultimo_fallo = _fallos.get(song_id)
        if ultimo_fallo and time.time() - ultimo_fallo < FRACASO_TTL:
            raise RuntimeError(f"descarga de {song_id} fallo hace poco; reintenta en unos segundos")

        cmd = [
            "yt-dlp", "-x", "--audio-format", "wav",
            "--postprocessor-args", "ffmpeg:-ac 2 -ar 44100",
            "--no-playlist", "--retries", "3",
            "--download-sections", f"*0-{MAX_SEGUNDOS}",
            "-o", str(CACHE_DIR / f"{song_id}.%(ext)s"),
            url,
        ]
        for intento in range(REINTENTOS):
            try:
                subprocess.check_call(cmd)
                break
            except subprocess.CalledProcessError:
                _limpiar_parciales(song_id)
                if intento == REINTENTOS - 1:
                    _fallos[song_id] = time.time()
                    raise
                print(f"[WARN] yt-dlp fallo para {song_id} (intento {intento + 1}); reintentando...")

        if not destino.exists():
            _fallos[song_id] = time.time()
            raise RuntimeError(f"yt-dlp termino bien pero no genero {destino.name}")

        _fallos.pop(song_id, None)
    return destino

def offset_a_segundos(offset_frames) -> float:
    try:
        frames = int(offset_frames)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, frames * HOP / SR)

def verificar_genero(cancion: str, source_url: str = "") -> str:
    json_file = Path(__file__).resolve().with_name("catalog.json")
    with json_file.open(encoding="utf-8") as f:
        data = json.load(f)

    if source_url:
        for entry in data.values():
            if entry.get("source_url") == source_url:
                return entry.get("genre") or "Desconocido"

    for entry in data.values():
        if entry.get("title") == cancion:
            return entry.get("genre") or "Desconocido"
        
    return "Desconocido"


# === ENDPOINTS ====
@app.post("/detectar")
def detectar(request: Request, audio: UploadFile = File(...)):
    print("Empezando a detectar...")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio.file.read())
        path = tmp.name
    try:
        resultados = detectar_cancion(path)
    finally:
        Path(path).unlink(missing_ok=True)

    if not resultados or resultados[0]["score"] < MIN_SCORE_CONFIABLE:
        return {"encontrada": False, "candidatos": resultados}

    top = resultados[0]
    print(top)
    sid = str(top["song_id"])
    url = top["source_url"]
    URLS[sid] = url

    # Dentro de que segundo de la cancion empieza lo que acaba de grabar el micrófono
    offset_frames = int(top.get("offset_frames") or 0)
    offset_seg = offset_a_segundos(offset_frames)
    seg_yt = max(0, int(round(offset_seg)))   # mismo valor para el navegador y para el TTS

    return {
        "encontrada": True,
        "name": top["name"],
        "score": top["score"],
        "genre": verificar_genero(top["name"], url),
        "offset_frames": offset_frames,
        "offset_seconds": round(offset_seg, 2),
        "minuto": "%d:%02d" % (seg_yt // 60, seg_yt % 60),
        "youtube_url": url_youtube_en(url, seg_yt),
        "play_url": str(request.url_for("audio", song_id=sid)),  # opcional: WAV bajo demanda
    }

@app.get("/audio/{song_id}")
def audio(song_id: str):
    url = URLS.get(song_id)
    if not url:
        raise HTTPException(404, "canción desconocida")
    try:
        path = asegurar_audio(song_id, url)
    except (subprocess.CalledProcessError, RuntimeError, FileNotFoundError) as e:
        print(f"[ERROR] /audio/{song_id}: {e}")
        raise HTTPException(502, "no se pudo descargar el audio")
    return FileResponse(path, media_type="audio/wav")


@app.get("/health")
def health():
    cacheadas = sorted(p.stem for p in CACHE_DIR.glob("*.wav"))
    return {
        "status": "ok",
        "canciones_cacheadas": len(cacheadas),
        "song_ids": cacheadas,
    }


# Corre con:
# uvicorn endpoint:app --host 0.0.0.0 --port 8000