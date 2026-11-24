import os
import sys
import torch
import joblib
import librosa
import tempfile
import numpy as np
import streamlit as st
from pathlib import Path
from huggingface_hub import hf_hub_download

os.environ.setdefault("USE_TF", "0")  # -> esto es solo pa mi local... si en el tuyo TensorFlow funciona, entonces borra esto p rctm
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"
sys.path.insert(0, str(PROJECT_ROOT ))  # para importar de deteccion_canciones.*

from deteccion_canciones.utils.hashing import hashes
from deteccion_canciones.utils.patterns import peaks
from deteccion_canciones.utils.spectrogram import generate_spectrogram
from deteccion_canciones.utils.fingerprint_db import get_connection, identify
from recomendacion_canciones.main_recomendar import MIN_SCORE_FINGERPRINT, recomendar

# Configuracion inicial para deteccion de canciones
SR, HOP = 11025, 512

# Configuracion para clasificador de genero
GENERO_MODEL_ID = "pollitoconpapass/genre-classifier-peruvian-music-ast-v1"
GENERO_SR = 16000
GENERO_CLIP = int(GENERO_SR * 10.24)
GENERO_DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

def detectar_cancion(audio_file_path: str)-> list:
    conn = get_connection(DB_PATH)
    hashes_query = hashes(peaks(generate_spectrogram(audio_file_path)))
    resultados = identify(conn, hashes_query, top_k=5, min_score=5, max_hash_freq=2000)
    return resultados

def _con_archivo_temp(wav_bytes: bytes, fn) -> list:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(wav_bytes)
        ruta = tmp.name
    try:
        return fn(ruta) or []
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass


@st.cache_data(show_spinner=False, max_entries=20)
def analizar(wav_bytes: bytes) -> list:
    return _con_archivo_temp(wav_bytes, detectar_cancion)


@st.cache_data(show_spinner=False, max_entries=20)
def recomendar_canciones(wav_bytes: bytes, detectada: str | None) -> list:
    return _con_archivo_temp(wav_bytes, lambda ruta: recomendar(ruta, cancion_detectada=detectada))


@st.cache_resource(show_spinner="Cargando el clasificador de género...")
def _cargar_clasificador_genero():
    encoder = joblib.load(hf_hub_download(repo_id=GENERO_MODEL_ID, filename="label_encoder.joblib"))
    modelo = AutoModelForAudioClassification.from_pretrained(GENERO_MODEL_ID).to(GENERO_DEVICE).eval()
    extractor = AutoFeatureExtractor.from_pretrained(GENERO_MODEL_ID)
    return modelo, extractor, encoder


def _ventanas_genero(y: np.ndarray) -> list[np.ndarray]:
    if len(y) < GENERO_CLIP:
        return [np.pad(y, (0, GENERO_CLIP - len(y)))]
    inicios = list(range(0, len(y) - GENERO_CLIP + 1, GENERO_CLIP))
    if len(y) - (inicios[-1] + GENERO_CLIP) >= int(0.5 * GENERO_SR):
        inicios.append(len(y) - GENERO_CLIP)
    return [y[s:s + GENERO_CLIP] for s in inicios]


def _clasificar_genero(ruta_audio: str) -> tuple[str, dict]:
    y, _ = librosa.load(ruta_audio, sr=GENERO_SR, mono=True, duration=15)
    if len(y) < GENERO_CLIP:
        y = np.pad(y, (0, GENERO_CLIP - len(y)))
    modelo, extractor, encoder = _cargar_clasificador_genero()
    clips = _ventanas_genero(y)
    X = np.stack([extractor(c, sampling_rate=GENERO_SR)["input_values"][0] for c in clips]).astype(np.float32)
    with torch.inference_mode():
        logits = modelo(input_values=torch.from_numpy(X).to(GENERO_DEVICE)).logits
    proba = torch.softmax(logits, dim=1).mean(0).cpu().numpy()
    orden = np.argsort(proba)[::-1]
    return str(encoder.classes_[orden[0]]), {str(encoder.classes_[i]): float(proba[i]) for i in orden}


@st.cache_data(show_spinner=False, max_entries=20)
def clasificar_genero(wav_bytes: bytes) -> tuple[str, dict]:
    return _con_archivo_temp(wav_bytes, _clasificar_genero)


# UI de Streamlit
st.set_page_config(page_title="Shazam Peru", page_icon="🇵🇪", layout="centered")
st.title("Shazam para musica peruana 🇵🇪")
st.caption("Shazam para música peruana: graba o sube un fragmento y te decimos qué canción es..")

audio = st.audio_input("Graba unos 10 segundos de la canción", sample_rate=SR)

if audio is not None:
    wav_bytes = audio.getvalue()

    # Reproducir el audio grabado para verificar (y en caso el usuario quiera descargarlo...)
    st.audio(wav_bytes, format="audio/wav")

    # # Guardar temporalmente como .wav y pasar la ruta a detectar_cancion
    # with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
    #     tmp.write(wav_bytes)
    #     ruta_wav = tmp.name

    try:
        with st.spinner("Analizando el audio..."):
            resultados = analizar(wav_bytes)
    except Exception as e:
        st.error(f"Ocurrió un error al analizar el audio: {e}")
        resultados = []

    if not resultados:
        st.warning("No se encontraron coincidencias. Intenta grabar un fragmento más largo o con menos ruido.")
    else:
        # Top Coincidencia (esa seria la canción... esperemos)
        top = resultados[0]
        score_pct = top["score"]
        segundos = segundos = max(0, int(top["offset_frames"] * HOP / SR)) 

        st.success(f"**{top['name']}**")
        st.caption(f"Score: {top['score']} · tu fragmento empieza en el minuto {segundos // 60}:{segundos % 60:02d}")
        if top["source_url"]:
            st.video(top["source_url"], start_time=segundos)

        if len(resultados) > 1:
            with st.expander("Otras coincidencias"):
                for r in resultados[1:]:
                    nombre = f"[{r['name']}]({r['source_url']})" if r["source_url"] else r["name"]
                    st.markdown(f"- {nombre} (score {r['score']})")

    # Reutilizar la deteccion hecha anteriormente
    detectada = resultados[0]["name"] if resultados and resultados[0]["score"] >= MIN_SCORE_FINGERPRINT else None

    # Recomendaciones por similitud de audio (MERT + Pinecone)
    with st.spinner("Buscando canciones parecidas..."):
        try:
            recomendaciones = recomendar_canciones(wav_bytes, detectada)
        except Exception as e:
            st.warning(f"No se pudieron generar recomendaciones: {e}")
            recomendaciones = []

    if recomendaciones:
        st.subheader("Canciones que podrían gustarte")
        etiquetas = [f"{r['name']} · {r['genre']}" for r in recomendaciones]
        elegida = st.pills("Canciones parecidas", etiquetas, default=etiquetas[0], label_visibility="collapsed")
        r = recomendaciones[etiquetas.index(elegida)] if elegida else None
        if r and r["source_url"]:
            st.video(r["source_url"])
            st.caption(f"[Ver en YouTube]({r['source_url']})")
        elif r:
            st.write(r["name"])

    # Clasificacion de genero musical (AST)
        with st.spinner("Clasificando el género musical..."):
            try:
                genero, probabilidades = clasificar_genero(wav_bytes)
            except Exception as e:
                st.warning(f"No se pudo clasificar el género: {e}")
                genero, probabilidades = None, {}
    
        if genero:
            st.subheader("Género musical estimado")
            st.markdown(f"### {genero}")
            st.bar_chart(probabilidades) 