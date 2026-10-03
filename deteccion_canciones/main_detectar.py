from pathlib import Path
from utils.hashing import hashes
from utils.patterns import peaks
from utils.spectrogram import generate_spectrogram
from utils.fingerprint_db import get_connection, identify

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"

conn = get_connection(str(DB_PATH))

hashes_query = hashes(peaks(generate_spectrogram("grabacion.wav")))
resultados = identify(conn, hashes_query, top_k=5, min_score=5)

print(resultados)