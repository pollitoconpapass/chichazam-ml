import time
import random
import yt_dlp
from yt_dlp.utils import DownloadError
from config.config_ytdlp import BASE_YDL_OPTS
from config.constants import MAX_DOWNLOAD_RETRIES, AUDIO_DIR, MIN_SLEEP, MAX_SLEEP
from .helpers import audio_path, file_is_valid, save_catalog, now_iso

def download_track(track): # -> descargar una cancion individual
    track_id = track["id"]
    title = track["title"]
    duration = track["duration_seconds"]

    output_file = audio_path(track_id)

    # Si ya existe la cancion y es valida... no hacemos nada
    if file_is_valid(output_file, expected_duration=duration):
        print(f"✓ Ya existe: {title}")
        return True

    # Obtener URL
    url = track["source_url"]
    if not url:
        print(f"✗ No hay URL para {title}")
        return False


    # Opciones especificas para la descarga
    opts = {
        **BASE_YDL_OPTS,
        "noplaylist": True,
        "outtmpl": str(AUDIO_DIR / "%(id)s.%(ext)s"),
    }

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            print(f"\n⬇ [{attempt}/{MAX_DOWNLOAD_RETRIES}] {title}")

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])


            # Validacion despues de descargar (que la duracion sea correcta)
            if file_is_valid(output_file, expected_duration=duration):
                print(f"✓ Descarga validada: {title}")
                return True

            else:
                print(f"✗ El archivo descargado no pasó la validación: {title}")

        # En caso haya error (ojala q ya no csm)
        except DownloadError as e:
            error_text = str(e)
            print(f"\n✗ Error descargando {title}: {error_text}")

            lower_error = error_text.lower()

            blocked = any(
                keyword in lower_error
                # Por si es el 403 de YouTube
                for keyword in [
                    "403",
                    "forbidden",
                    "sign in",
                    "bot",
                    "captcha",
                    "confirm you're not a bot",
                ]
            )

            if blocked:
                print("\n⚠ YouTube rechazó la solicitud.")
                print("No se realizarán retries agresivos.")
                return False

            if attempt < MAX_DOWNLOAD_RETRIES:
                wait = 15 * attempt
                print(f"Esperando {wait}s...")
                time.sleep(wait)

    return False


def download_pending_tracks(catalog): # -> descargar todas las canciones pendientes
    tracks = list(catalog.values())
    pending = [
        track
        for track in tracks
        if track.get("status") == "pending"
    ]

    print()
    print("=" * 70)
    print("DOWNLOAD")
    print("=" * 70)

    print(f"Pendientes: {len(pending)}")

    for index, track in enumerate(pending, start=1):
        print(f"\n[{index}/{len(pending)}]")

        # Descargar usando la funcion de arrbia
        success = download_track(track)

        if success:
            track["status"] = "downloaded"
            track["downloaded_at"] = now_iso()
            track["error"] = None
        else:
            track["status"] = "error"
            track["error"] = "Download failed or validation failed"

        # Guardar
        save_catalog(catalog)

        # Hacer una pausa...
        if index < len(pending):
            sleep_time = random.uniform(MIN_SLEEP, MAX_SLEEP) # -> Numeros de segundo aleatorios...
            print(f"Esperando {sleep_time:.1f}s...")
            time.sleep(sleep_time)