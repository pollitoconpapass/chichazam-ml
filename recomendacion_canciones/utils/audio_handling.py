import json
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
from huggingface_hub import snapshot_download

DATASET_ID = "pollitoconpapass/dataset-peru-shazam"
SR = 24_000          # MERT trabaja a 24 kHz
CHUNK_SECONDS = 10   # ventana que espera CLAP
HOP_SECONDS = 5      # 50 % de solapamiento entre ventanas


def download_dataset() -> Path:
    return Path(snapshot_download(repo_id=DATASET_ID, repo_type="dataset"))


def load_catalog(dataset_dir: Path) -> list[dict]:
    catalog = json.loads((dataset_dir / "catalog.json").read_text(encoding="utf-8"))
    validos = [e for e in catalog.values() if e.get("status") == "downloaded" and not e.get("error")]
    repeticiones = Counter(e["title"] for e in validos)
    for entry in validos:
        entry["name"] = entry["title"] if repeticiones[entry["title"]] == 1 else f'{entry["title"]} ({entry["id"]})'
    return validos


def load_audio(path: str | Path) -> np.ndarray:
    y, _ = librosa.load(path, sr=SR, mono=True)
    return y.astype(np.float32)


def chunks(y: np.ndarray) -> list[tuple[np.ndarray, int]]: # -> Ventanas de 10 s cada 5 s -> [(audio, segundo_inicial), ...]. Si el audio dura menos de 10 s se devuelve entero (el extractor lo rellena). El resto final (< 5 s) se descarta.
    size, hop = CHUNK_SECONDS * SR, HOP_SECONDS * SR
    return [(y[s:s + size], s // SR) for s in range(0, len(y) - size + 1, hop)] or [(y, 0)]
