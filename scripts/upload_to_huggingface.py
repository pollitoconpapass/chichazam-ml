import os
import sys
import json
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi, create_repo, upload_file, upload_folder, login

# Config contants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "recoleccion_datos" / "dataset_peru_shazam"
CATALOG_PATH = DATASET_DIR / "catalog.json"
AUDIO_DIR = DATASET_DIR / "audio_tracks"

HF_REPO_ID = "pollitoconpapass/dataset-peru-shazam"
REPO_TYPE = "dataset"

# HF Credentials
load_dotenv(PROJECT_ROOT / ".env")
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    print("ERROR: HF_TOKEN not found in .env file.")
    print("Add it to .env: HF_TOKEN=hf_your_token_here")
    sys.exit(1)

# HF Auth
api = HfApi(token=HF_TOKEN)
login(token=HF_TOKEN)

# Loading catalog.json
print("Loading catalog...")
with open(CATALOG_PATH) as f:
    catalog = json.load(f)

downloaded = {k: v for k, v in catalog.items() if v["status"] == "downloaded"}
print(f"Total entries: {len(catalog)} | Downloaded: {len(downloaded)}")

# Creating HF repo 
genres = {}
for entry in downloaded.values():
    g = entry["genre"]
    genres[g] = genres.get(g, 0) + 1

genre_list = "\n".join(f"- **{g}**: {c} tracks" for g, c in sorted(genres.items()))

README_CONTENT = f"""---
tags:
- audio
- music
- peru
- shazam
- ethnomusicology
- folk-music
- cumbia-amazonica
- huayno
- chicha
task_categories:
- other
source_datasets:
- local
license: cc-by-nc-4.0
---

# Peru Shazam Dataset

A collection of Peruvian music tracks discovered via Shazam, covering traditional and popular genres from Peru.

## Dataset Summary

| Property | Value |
|----------|-------|
| Total tracks | {len(downloaded)} |
| Audio format | WAV (44.1kHz mono) |
| Genres | {len(genres)} |
| Source | YouTube (Shazam discovery) |

## Genre Distribution

{genre_list}

## Data Structure

```
dataset-peru-shazam/
├── README.md          # This file
├── catalog.json       # Full metadata (title, genre, duration, source URLs)
└── audio/             # WAV audio files (named by YouTube ID)
```

## catalog.json Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | YouTube video ID (used as filename) |
| `title` | string | Song title / description |
| `duration_seconds` | int | Track duration in seconds |
| `genre` | string | Music genre classification |
| `filename` | string | Audio filename |
| `source_url` | string | Original YouTube URL |


## Usage
As the `catalog.json` is important to check the audio metadata, this is the ideal way to use this dataset.
### Use of the Audio Data
```python
from datasets import load_dataset
ds = load_dataset("pollitoconpapass/dataset-peru-shazam")
sample = ds[0]['audio'] # -> This is the audio itself of the first item: <datasets.features._torchcodec.AudioDecoder object at 0x7ef124d88150>
```
You can use the `ds` variable as the audios dataset
### Use of the JSON catalog
```python
from datasets import load_dataset
catalog_json = load_dataset("pollitoconpapass/dataset-peru-shazam", data_files="catalog.json")
# When you apply data_files you can only use the file attached there...
json_content = catalog_json['train'][0] # -> this is the whole JSON object in catalog.json
print(json_content['R0V41zBH2xY'])
# Output of line above:
'''
{'id': 'R0V41zBH2xY',
 'title': 'Que linda flor - Silverio Urbina',
 'duration_seconds': 252,
 'genre': 'huayno',
 'filename': 'R0V41zBH2xY.wav',
 'source_url': 'https://www.youtube.com/watch?v=R0V41zBH2xY',
 'status': 'downloaded',
 'discovered_at': '2026-09-22T16:04:13.743392+00:00',
 'downloaded_at': '2026-09-22T17:11:16.063261+00:00',
 'error': None}
'''
```
You can use the `json_content` variable as the guide for all the audios present in the dataset


## License

CC-BY-NC-4.0 — For non-commercial research and educational use.
"""

print("Creating repository...")
create_repo(HF_REPO_ID, repo_type=REPO_TYPE, token=HF_TOKEN, exist_ok=True)

# Upload README
upload_file(
    path_or_fileobj=README_CONTENT.encode(),
    path_in_repo="README.md",
    repo_id=HF_REPO_ID,
    repo_type=REPO_TYPE,
    token=HF_TOKEN,
)
print("README.md uploaded.")

# Upload catalog
upload_file(
    path_or_fileobj=str(CATALOG_PATH),
    path_in_repo="catalog.json",
    repo_id=HF_REPO_ID,
    repo_type=REPO_TYPE,
    token=HF_TOKEN,
)
print("catalog.json uploaded.")

# ==== (ALL OF THIS WAS BECAUSE THE HF API WAS GIVING TIMEOUT ERRORS...) ====
print("\nChecking existing files in repo...")
existing_files = set(api.list_repo_files(HF_REPO_ID, repo_type=REPO_TYPE))

audio_files = sorted(AUDIO_DIR.glob("*.wav"))
to_upload = [f for f in audio_files if f.stem in downloaded and f"audio/{f.name}" not in existing_files]

print(f"Total on disk: {len(audio_files)} | Already in repo: {len(audio_files) - len(to_upload)} | Remaining: {len(to_upload)}")

if not to_upload:
    print("All files already uploaded!")
    print(f"Dataset: https://huggingface.co/datasets/{HF_REPO_ID}")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmpdir:
    staging_audio = Path(tmpdir) / "audio"
    staging_audio.mkdir()

    print(f"Staging {len(to_upload)} files...")
    for f in to_upload:
        os.symlink(f, staging_audio / f.name)

    print(f"Uploading {len(to_upload)} audio files in a single commit (this may take a while)...")
    upload_folder(
        folder_path=str(Path(tmpdir)),
        repo_id=HF_REPO_ID,
        repo_type=REPO_TYPE,
        token=HF_TOKEN,
        commit_message=f"Upload {len(to_upload)} audio tracks",
    )

# this no... this is the final message :)
print(f"\nDone! All {len(to_upload)} remaining files uploaded.")
print(f"Dataset: https://huggingface.co/datasets/{HF_REPO_ID}")
