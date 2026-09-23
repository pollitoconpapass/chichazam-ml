from config.constants import AUDIO_DIR, METADATA_FILE

def print_statistics(catalog):
    total = len(catalog)
    statuses = {}

    for track in catalog.values():
        status = track.get("status", "unknown")

        statuses[status] = (statuses.get(status, 0) + 1)

    print("=" * 70)
    print("DATASET STATISTICS")
    print("=" * 70)

    print(f"Total: {total}")

    for status, count in statuses.items():
        print(f"{status:20s}: {count}")

    print(f"Audio directory: {AUDIO_DIR}")
    print(f"Catalog: {METADATA_FILE}")