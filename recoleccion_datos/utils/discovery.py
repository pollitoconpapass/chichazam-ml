import yt_dlp
from .helpers import now_iso
from yt_dlp.utils import DownloadError
from config.config_ytdlp import BASE_YDL_OPTS
from config.constants import MAX_DURATION

def discover_playlist(url, genre): # -> obtener las canciones de una playlist (sin descargar los audios). Devuelve lista de canciones
    print("=" * 70)
    print(f"DISCOVERY: {genre}")
    print("=" * 70)

    opts = {
        **BASE_YDL_OPTS,
        # Discovery = NO descargar
        "skip_download": True,
        # No necesitamos postprocesamiento
        "quiet": False,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            print("⚠ No se pudo obtener información.")
            return []

        entries = info.get("entries", [])
        results = []

        for entry in entries:
            if not entry:
                continue

            track_id = entry.get("id")
            if not track_id:
                continue

            title = entry.get("title")
            duration = entry.get("duration")
            webpage_url = entry.get("webpage_url")

            # Estado inicial
            if duration and duration > MAX_DURATION:
                status = "skipped_long"
            else:
                status = "pending"

            results.append(
                {
                    "id": track_id,
                    "title": title,
                    "duration_seconds": duration,
                    "genre": genre,
                    "filename": f"{track_id}.wav",
                    "source_url": webpage_url,
                    "status": status,
                    "discovered_at": now_iso(),
                    "downloaded_at": None,
                    "error": None,
                }
            )

        print(f"✓ Encontradas {len(results)} canciones candidatas.")
        return results

    except DownloadError as e:
        print(f"Error durante discovery: {e}")
        return []


def merge_discovery_into_catalog(catalog, discovered_tracks): # -> añadir las canciones descubiertas al catalogo (sin sobreescribir las existentes)
    added = 0

    for track in discovered_tracks:
        track_id = track["id"]
        if track_id not in catalog:
            catalog[track_id] = track
            added += 1

        else: # -> Se actualiza solo la metadata...
            existing = catalog[track_id]

            existing["title"] = track["title"]
            existing["duration_seconds"] = (
                track["duration_seconds"]
            )
            existing["genre"] = track["genre"]
            existing["source_url"] = track["source_url"]

    return added