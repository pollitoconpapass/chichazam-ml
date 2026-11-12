import os

os.environ.setdefault("USE_TF", "0") # -> solo pa mi entorno que esta roto TensorFlow
from pathlib import Path

import torch
import numpy as np
from utils.audio_handling import SR
from transformers import AutoModel, Wav2Vec2FeatureExtractor


MODEL_ID = "m-a-p/MERT-v1-95M"  # encoder musical; CLAP separaba mal los generos peruanos
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
BATCH_SIZE = 8
MEAN_PATH = Path(__file__).resolve().parent.parent / "embedding_mean.npy"

_model = None
_processor = None


def _load():
    global _model, _processor
    if _model is None:
        _processor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_ID, trust_remote_code=True)
        _model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True).to(DEVICE).eval()
    return _model, _processor


@torch.inference_mode()
def embed(audios: list[np.ndarray], batch_size: int = BATCH_SIZE) -> np.ndarray: # -> audios mono a 24 kHz -> matriz (n, 768) normalizada en L2.
    model, processor = _load()
    out = []
    for i in range(0, len(audios), batch_size):
        inputs = processor(audios[i:i + batch_size], sampling_rate=SR,
                           return_tensors="pt", padding=True).to(DEVICE)
        hidden = model(**inputs, output_hidden_states=True).hidden_states
        
        pooled = torch.stack(hidden[-4:]).mean(0).mean(dim=1) # promedio de las ultimas 4 capas y del tiempo (mejor que solo la ultima capa)
        out.append(pooled.cpu().float().numpy())

    matrix = np.concatenate(out)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def save_mean(vectors: np.ndarray) -> np.ndarray:
    mean = vectors.mean(axis=0)
    np.save(MEAN_PATH, mean)
    return mean


def load_mean() -> np.ndarray:
    return np.load(MEAN_PATH)


def center(vectors: np.ndarray, mean: np.ndarray) -> np.ndarray: # -> resta el vector medio del corpus y renormaliza: sin esto las similitudes se comprimen
    centered = vectors - mean
    return centered / np.linalg.norm(centered, axis=1, keepdims=True)
