# HOW TO: Manejo del dataset de Hugging Face

El dataset donde se encuentran todas las canciones junto con su metadata se llama: `pollitoconpapass/dataset-peru-shazam`. Son un total de 318 canciones.

## Estructura

La estructura del dataset es el siguiente:

```
dataset-peru-shazam/
├── README.md
├── catalog.json       # Full metadata (title, genre, duration, source URLs)
└── audio/             # Archivos de audio WAV (nombrados por Youtube IDs)
```

Campos del `catalog.json`:
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `id` | string | ID de youtube del video (usado como nombre del archivo) |
| `title` | string | Titulo de la cancion |
| `duration_seconds` | int | Duracion en segundos |
| `genre` | string | Genero de música |
| `filename` | string | Nombre del audio (id.wav) |
| `source_url` | string | URL del video de YouTube |

## Uso

Este es un ejemplo de como usar el presente dataset para operar con tanto el audio como su metadata.

```python
# Cargar el JSON de metadata
catalog_dataset = load_dataset("pollitoconpapass/dataset-peru-shazam", data_files="catalog.json")

# Extraer el contenido y convertirlo a dataframe
json_content = catalog_dataset['train'][0]
df_metadata = pd.DataFrame.from_dict(json_content, orient='index')

# Filtrar solo las que tienen el status: downloaded
catalog_dataset = load_dataset("pollitoconpapass/dataset-peru-shazam", data_files="catalog.json")
json_content = catalog_dataset['train'][0]
df_metadata = pd.DataFrame.from_dict(json_content, orient='index')

df_validos = df_metadata[(df_metadata['status'] == 'downloaded') & (df_metadata['error'].isnull())]

# Cargar dataset de audios (datos de los audios como tal, ya no la metadata)
ds_audio = load_dataset("pollitoconpapass/dataset-peru-shazam")
audio_split = ds_audio['train'] if 'train' in ds_audio else ds_audio

# Asegurar de utilizar la metadata de solo aquellos que fueron descargados correctamente
df_validos = df_metadata[(df_metadata['status'] == 'downloaded') & (df_metadata['error'].isnull())].reset_index(drop=True)

# Vincular tanto audio como metadata
print("ID del primer registro en el JSON filtrado:", df_validos.iloc[0]['id'])
print("Título:", df_validos.iloc[0]['title'])

# Propiedades del primero
primer_audio_obj = audio_split[0]['audio']
print("Propiedades del objeto audio:", dir(primer_audio_obj))

# Asignamos los metadatos correspondientes según el índice
def agregar_metadatos(example, idx):
    row = df_validos.iloc[idx]
    example['id'] = row['id']
    example['title'] = row['title']
    example['genre'] = row['genre']
    example['source_url'] = row['source_url']
    return example

# Aplicamos la fusión en el dataset de audio (combinar ambos)
audio_con_metadatos = audio_split.map(agregar_metadatos, with_indices=True)

# Muestra
print("Muestra 0 unificada:")
print(f"ID: {audio_con_metadatos[1]['id']}")
print(f"Título: {audio_con_metadatos[1]['title']}")
print(f"Género: {audio_con_metadatos[1]['genre']}")
```
