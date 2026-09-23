from .constants import AUDIO_DIR, SAMPLE_RATE, CHANNELS, BROWSER, MAX_DURATION

def skip_mixes(info, *, incomplete):
    duration = info.get("duration")

    if duration and duration > MAX_DURATION:
        return (f"Video demasiado largo... ({duration:.0f}s > {MAX_DURATION}s)")

    return None


BASE_YDL_OPTS = {
    # Mejor audio disponible
    "format": "bestaudio/best",

    # Conversión a WAV
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }
    ],

    # Normalización del audio
    "postprocessor_args": [
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
    ],

    # Nombre temporal
    # El archivo final será posteriormente .wav
    "outtmpl": str(AUDIO_DIR / "%(id)s.%(ext)s"),

    # Comportamiento
    "quiet": False,
    "ignoreerrors": True,

    # Filtro de duración
    "match_filter": skip_mixes,

    # Cookies directamente desde Brave
    "cookiesfrombrowser": (BROWSER,),

    # Metadata
    "writethumbnail": False,
    "writesubtitles": False,

    # Evitar archivos parciales antiguos
    "continuedl": True,
}