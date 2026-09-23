import json
import subprocess
from datetime import datetime, timezone
from config.constants import AUDIO_DIR, METADATA_FILE, SAMPLE_RATE, CHANNELS


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_catalog():
    if not METADATA_FILE.exists():
        return {}

    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except json.JSONDecodeError:
        print("⚠ catalog.json está corrupto.")
        print("Se utilizará un catálogo vacío.")

        return {}


def save_catalog(catalog):
    temp_file = METADATA_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            catalog,
            f,
            ensure_ascii=False,
            indent=2
        )

    # Reemplazo atómico
    temp_file.replace(METADATA_FILE)


def audio_path(track_id):
    return AUDIO_DIR / f"{track_id}.wav"


def file_is_valid(path, expected_duration=None):
    if not path.exists():
        return False

    # Archivo demasiado pequeño probablemente indica una descarga rota.
    if path.stat().st_size < 10_000:
        return False

    try:

        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,duration",
            "-of",
            "json",
            str(path)
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False

        data = json.loads(result.stdout)

        streams = data.get("streams", [])

        if not streams:
            return False

        stream = streams[0]

        codec = stream.get("codec_name")
        sample_rate = int(stream.get("sample_rate", 0))
        channels = int(stream.get("channels", 0))

        if codec != "pcm_s16le":
            print(f"⚠ Codec inesperado: {codec}")

        if sample_rate != SAMPLE_RATE:
            print(f"⚠ Sample rate inesperado: {sample_rate} Hz")

        if channels != CHANNELS:
            print(f"⚠ Número de canales inesperado: {channels}")

        duration = stream.get("duration")

        if duration:
            duration = float(duration)

            # Evitamos comparar demasiado estrictamente.
            if expected_duration:
                difference = abs(duration - expected_duration)

                if difference > 10:
                    print(
                        f"⚠ Diferencia de duración: "
                        f"esperada={expected_duration:.1f}s "
                        f"real={duration:.1f}s"
                    )

        return True

    except Exception as e:
        print(f"⚠ Error validando {path}: {e}")
        return False
