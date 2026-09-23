from pathlib import Path

OUTPUT_DIR = Path("./dataset_peru_shazam")
AUDIO_DIR = OUTPUT_DIR / "audio_tracks"
METADATA_FILE = OUTPUT_DIR / "catalog.json"

# Navegador utilizado para las cookies.
# Opciones comunes: "brave", "chrome", "firefox", "edge"
BROWSER = "brave"

# Máximo de duración aceptada.
# > 600 segundos = posible mix / recopilación
MAX_DURATION = 600

# Formato final
SAMPLE_RATE = 22050
CHANNELS = 1

# Pausas entre descargas
MIN_SLEEP = 8
MAX_SLEEP = 20

# Si una descarga falla, no insistir inmediatamente demasiadas veces.
MAX_DOWNLOAD_RETRIES = 2

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)