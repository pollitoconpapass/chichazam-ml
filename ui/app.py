import os
import sys
import tempfile
import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "fingerprints.db"
sys.path.insert(0, str(PROJECT_ROOT ))  # para importar de deteccion_canciones.*

from deteccion_canciones.utils.hashing import hashes
from deteccion_canciones.utils.patterns import peaks
from deteccion_canciones.utils.spectrogram import generate_spectrogram
from deteccion_canciones.utils.fingerprint_db import get_connection, identify

# Configuracion inicial para deteccion de canciones
SR, HOP = 11025, 512

def detectar_cancion(audio_file_path: str)-> list:
    conn = get_connection(DB_PATH)
    hashes_query = hashes(peaks(generate_spectrogram(audio_file_path)))
    resultados = identify(conn, hashes_query, top_k=5, min_score=5, max_hash_freq=2000)
    return resultados

@st.cache_data(show_spinner=False, max_entries=20)
def analizar(wav_bytes: bytes) -> list:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(wav_bytes)
        ruta = tmp.name
    try:
        return detectar_cancion(ruta) or []
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass


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