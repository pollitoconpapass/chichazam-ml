FAN_OUT, DT_MAX = 6, 200 
# FAN_OUT: Cada pico "ancla" se empareja con los picos que siguen para formar pares
# DT_MAX: Filtra pares demasiado separados. Si dos puntos son mas separados que esto... significa que no son parte de la misma caracteristica de la cancion y no deberian formar un hash

# Generar los hashes a partir de los picos
def hashes(pts):
    out = []
    for i, (t1, f1) in enumerate(pts): # -> empieza desde el ancla y mira los siguientes 18 picos (FAN_OUT*3) para formar pares
        for t2, f2 in pts[i+1:i+1+FAN_OUT*3]: # -> mira 18 candidatos ademas del filtro
            dt = t2 - t1 # -> diferencia de tiempo entre picos
            if 0 < dt <= DT_MAX:
                h = (f1 << 23) | (f2 << 14) | dt # -> el hash... ese 23 y 14 significa que se usan 9 bits para dt, 9 bits para f2 y 9 bits para f1.
                out.append((h, t1)) # -> se guarda el hash y el tiempo del primer pico
    return out

# Pq 9 bits? pq 2^9 = 512, y el maximo de frecuencia es 512 (ver BANDS en patterns.py).