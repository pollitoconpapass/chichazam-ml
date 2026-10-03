import numpy as np

BANDS = [(0,10),(10,20),(20,40),(40,80),(80,160),(160,512)] # -> mientras mas pequeño menos perceptible para el oido humano, pero mas sensible a ruido y distorsion. 512 es el maximo para N_FFT=1024

# Obtener los picos mas altos de un espectograma por banda de frecuencia
def peaks(spectogram):
    pts = []
    for t in range(spectogram.shape[1]):
        cands = []
        for lo, hi in BANDS:
            f = lo + np.argmax(spectogram[lo:hi, t])
            cands.append((f, spectogram[f, t]))

        thr = np.mean([m for _, m in cands]) # -> umbral de magnitud para considerar un pico como tal (si no lo supera, se descarta). 
                                            # -> Esto ayuda con el ruido ya que los picos de ruido suelen ser mas bajos que los picos de la señal real.
        pts += [(t, f) for f, m in cands if m > thr]

    return pts  # ya viene ordenado por t