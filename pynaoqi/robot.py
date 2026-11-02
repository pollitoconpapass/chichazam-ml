import os
import time
import webbrowser
import requests
import subprocess
from naoqi import ALProxy
from dances import bailar

# === CONFIG ROBOT ===
NAO_IP = "10.164.81.90" # "172.22.200.36" 
NAO_PORT = 9561
API_BASE = "http://0.0.0.0:8000"

SEGUNDOS_GRABACION = 15
REPRODUCIR = True 

REMOTE_DIR = "/home/nao/recordings"
REMOTE_WAV = REMOTE_DIR + "/cancion.wav"
LOCAL_WAV = "cancion.wav"

MODO = "mac" # ->  "robot" | "mac" | "comparar"
MAC_WAV = "cancion_mac.wav"
MAC_DEVICE = ":0" 
DEVNULL = open(os.devnull, "w")


# === HELPER ===
def limpiar_nombre(name): # -> funcion de ayuda para limpiar los nombres de las canciones
    base = os.path.splitext(name)[0]
    return base.replace("_", " ").strip()

def abrir_en_youtube(url):
    print("[YouTube] Abriendo: %s" % url)
    webbrowser.open(url)


# === FUNCIONES MANEJANDO EL NAO ===
def decir(tts, texto):
    if tts is None:
        print("[TTS off] %s" % texto)
        return
    unicode = getattr(__builtins__, "unicode", str)
    if isinstance(texto, unicode):
        texto = texto.encode("utf-8")
    tts.say(texto)

# === FUNCIONES GRABACIONES ===
def grabar_en_robot():
    rec = ALProxy("ALAudioRecorder", NAO_IP, NAO_PORT)
    try:
        rec.stopMicrophonesRecording()
    except Exception:
        pass

    rec.startMicrophonesRecording(REMOTE_WAV, "wav", 16000, [0, 0, 1, 0])
    time.sleep(SEGUNDOS_GRABACION)
    rec.stopMicrophonesRecording()

def _ffmpeg_mac(segundos):
    return [
        "ffmpeg", "-y",
        "-f", "avfoundation", "-i", MAC_DEVICE,
        "-t", str(segundos),
        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
        MAC_WAV,
    ]

def grabar_en_mac():
    subprocess.check_call(_ffmpeg_mac(SEGUNDOS_GRABACION),
                          stdout=DEVNULL, stderr=DEVNULL)

def grabar_ambos():
    rec = ALProxy("ALAudioRecorder", NAO_IP, NAO_PORT)
    try:
        rec.stopMicrophonesRecording()
    except Exception:
        pass
    rec.startMicrophonesRecording(REMOTE_WAV, "wav", 16000, [0, 0, 1, 0])
    p = subprocess.Popen(_ffmpeg_mac(SEGUNDOS_GRABACION),
                         stdout=DEVNULL, stderr=DEVNULL)
    p.wait()
    rec.stopMicrophonesRecording()


# === FUNCIONES DETECCION ===
def detectar_en_servidor(path):
    with open(path, "rb") as f:
        r = requests.post(
            API_BASE + "/detectar",
            files={"audio": ("cancion.wav", f, "audio/wav")},
            timeout=90,
        )
    r.raise_for_status()
    return r.json()

def resumen(etiqueta, data):
    if data.get("encontrada"):
        print("[%s] %s (score %s)" % (etiqueta, data["name"], data["score"]))
    else:
        cands = data.get("candidatos") or []
        mejor = cands[0]["score"] if cands else 0
        print("[%s] no reconocida (mejor score: %s)" % (etiqueta, mejor))

# === MAIN ===
def main():
    try:
        tts = ALProxy("ALTextToSpeech", NAO_IP, NAO_PORT)
        motion = ALProxy("ALMotion", NAO_IP, NAO_PORT)
        tts.setLanguage("English") # IDIOMA GAAAA
    except Exception as e:
        print("[WARN] Sin robot para el habla (%s); sigo solo en consola." % e)
        tts = None

    decir(tts, "Hola! Soy NaoShazam, y voy a detectar tu cancion. Puedes reproducirla ahora.")

    # Cambiar grabacion por MODO
    if MODO == "mac":
        grabar_en_mac()
        archivo = MAC_WAV
    elif MODO == "robot":
        grabar_en_robot()
        if not os.path.exists(LOCAL_WAV):
            print("[ERROR] No existe %s localmente: la grabacion del robot quedo en el NAO "
                  "(hoy no hay forma de bajarla sin SSH con clave publica). Usando MODO='mac'." % LOCAL_WAV)
            decir(tts, "No pude bajar la grabacion, voy a usar el microfono de la Mac.")
            grabar_en_mac()
            archivo = MAC_WAV
        else:
            archivo = LOCAL_WAV
    else:
        grabar_ambos()
        decir(tts, "Dame un momento, estoy comparando los microfonos.")
        d_robot = detectar_en_servidor(LOCAL_WAV) if os.path.exists(LOCAL_WAV) else {"encontrada": False}
        d_mac = detectar_en_servidor(MAC_WAV)
        resumen("ROBOT", d_robot)
        resumen("MAC  ", d_mac)
        decir(tts, "Listo, revisa la consola.")
        return

    # Analzando la cancion
    decir(tts, "Dame un momento, estoy analizando.")
    try:
        data = detectar_en_servidor(archivo)
    except Exception as e:
        print("Error: %s" % e)
        decir(tts, "Tuve un problema al analizar la cancion.")
        return

    if not data.get("encontrada"):
        decir(tts, "No pude reconocer la cancion. Acercala mas a mi microfono.")
        return

    nombre = limpiar_nombre(data["name"])
    genero = data.get("genre")
    decir(tts, u"Esta cancion es " + nombre + u", del genero " + genero + u". Ahora voy a bailarla!")

    if REPRODUCIR and data.get("youtube_url"):
        print("[Detectado] %s | score %s | offset %s frames = %s s (minuto %s) | %s"
              % (nombre, data["score"], data.get("offset_frames"), data.get("offset_seconds"),
                 data.get("minuto"), data["youtube_url"]))
        decir(tts, "Abriendo en YouTube.")
        try:
            abrir_en_youtube(data["youtube_url"])
            
            bailar(motion, genero)
        except Exception as e:
            print("Error abriendo YouTube o ejecutando el baile: %s" % e)
            decir(tts, "No pude abrir YouTube o ejecutar el baile.")


if __name__ == "__main__":
    main()

# Correr con:
# naoqi-shell
# python2.7 robot.py