# Notas sobre cuestiones del proyecto

Aquí estarán algunas notas relacionadas a los dos módulos del proyecto. Más q todo para aclarar como se hizo la vaina (o como se piensa hacer...)

## Deteccion de canciones

### Ingestación

1. Usar la Transformada de Fourier de tiempo corto (STFT) para generar un espectograma a partir de la canción.
2. En el espectograma se perciben ciertos patrones... estos patrones son las caracteristicas del audio en el espectograma
3. Establecemos 6 bandas sonoras basadas en el nivel auditivo del ser humano: `[(0,10),(10,20),(20,40),(40,80),(80,160),(160,512)]`.
4. Para no procesar todos los puntos, en cada banda tomamos el pico mas fuerte y de esos sacamos un promedio simple. Aquellos puntos que no pasen ese promedio, se descartarán.
5. Este proceso sirve para reducir la memoria y el tiempo de procesamiento, pero también para manejar el ruidd ya que dificilmente el ruido sea mas alto que aquellos puntos que pasaron el promedio.
6. Ahora, cada punto "sobreviviente" va a hacer de ancla con todos los demás para generar relaciones. Pero, solo se generan relaciones, con los punto que estan despues en el tiempo y que no pasen un espacio de tiempo considerable (`DT_MAX`, Si dos puntos son mas separados que esto... significa que no son parte de la misma caracteristica de la cancion y no deberian formar un hash)
7. Se genera un hash por cada pareja ancla-vecino.
8. Para generar el hash, se empaqueta tanto la frecuencia del punto ancla + la frecuencia del punto vecino i + la diferencia de tiempo de ambos puntos (t_vecino - t_ancla). Ya que el vecino esta despues en el tiempo.
9. El valor del hash es un entero empaquetado de 32 bits... (frecuencias = 18 bits y la diferencia del tiempo = 14 -> (18x2) + 14 = 32)
10. Este hash se guarda dentro de la base de datos junto con el ID de la canción y el tiempo el punto ancla (el momento de la canción)

### Detección

1. Se hace el proceso de fingerprinting de la grabación de audio (fragmento de una canción a detectar).
2. Para cada hash de la grabacion se busca en la DB todas las filas con ese hash y arrojas todos los resultados posibles. ("Esta canción tiene este hash en el tiempo X")
3. Por cada resultado, se calcula la diferencia: `= tiempo_en_canción − tiempo_en_grabación`
4. Por canción, se cuenta cuantas mismas diferencias hay (un histograma de cantidades que cuenta cuantas veces aparece esa diferencia)
5. El score de cada canción es la cantidad mas alta de veces que aparece una diferencia (barra mas alta del histograma)

Ej:

Imagina que grabas 10 segundos que empiezan en el segundo 60 de la canción:
Hash | Tiempo en tu grabación | Tiempo en la canción | Diferencia |
|------|------------------------|----------------------|------------|
| h1 | 1 s | 61 s | 60 |
| h2 | 3 s | 63 s | 60 |
| h3 | 4 s | 64 s | 60 |
| h4 | 8 s | 68 s | 60 |

Como tu grabación es un trozo copiado de la canción, cada hash cae exactamente 60 s más adelante en la original. La diferencia es constante.

Ahora una canción incorrecta que comparte algunos hashes por pura casualidad:
| Hash | Tiempo en tu grabación | Tiempo en la otra canción | Diferencia |
|------|------------------------|---------------------------|------------|
| h2 | 3 s | 12 s | 9 |
| h4 | 8 s | 150 s | 142 |

"Si grabas un fragmento de una canción, los hashes de tu grabación aparecen en la canción original siempre con el mismo desfase de tiempo."

### Consideraciones Adicionales

Fourier (clásico) toma un trozo de sonido y te dice qué frecuencias (notas) contiene y con cuánta fuerza. Pero si la aplicas a la canción entera, solo sabes qué notas aparecen en total, no cuándo suenan, y para el fingerprint necesitas saber cuándo. Por eso es que se usa la Transformada de Fourier de tiempo corto (STFT) ya que resuelve eso cortando la canción en ventanas pequeñas y aplicando Fourier a cada una, obteniendo un espectograma con los valores de: eje X es el tiempo, el eje Y la frecuencia, y el valor es la intensidad.

## Recomendación de canciones

1. Crear embeddings de cada una de las canciones en el dataset
2. Subirlas a Pinecone con su metadata (titulo, genero, url)
3. Cuando el usuario reproduzca un fragmento de canción, hacer el embedding de ese audio
4. Consultar topk = 4 de similitudes de ese vector con los vectores de la base de datos
5. Mostrar los matches con su metadata
