from utils.discovery import discover_playlist, merge_discovery_into_catalog
from utils.downloads import download_pending_tracks
from utils.helpers import load_catalog, save_catalog
from utils.stats import print_statistics
from sources import SOURCES

# Si hay datos previos (en el json) lo cargamos
catalog = load_catalog()

print("=" * 70)
print("PERUVIAN MUSIC DATASET")
print("=" * 70)

print(f"Tracks existentes: {len(catalog)}")

# Buscar las canciones en cada playlist
for source in SOURCES:
    discovered = discover_playlist(source["url"], source["genre"])

    # Añadimos las canciones al dataset
    added = merge_discovery_into_catalog(catalog, discovered)
    save_catalog(catalog)
    print(f"✓ {added} nuevos tracks añadidos.")

# Por si hay algun error o descarga pendiente
download_pending_tracks(catalog)

# Guardar y mostrar stats
save_catalog(catalog)
print_statistics(catalog)