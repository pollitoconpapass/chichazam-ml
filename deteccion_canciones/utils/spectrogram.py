import librosa
import numpy as np
import librosa.display
import matplotlib.pyplot as plt

SR, N_FFT, HOP = 11025, 1024, 512 # -> SR: sample rate = 1025 para hacer un downsample, N_FFT: tamaño de la ventana para la Transformada de Fourier, HOP: Cuanto se mueve la ventana entre frames(N_FFT/2 = 512)

def generate_spectrogram(audio_file_path: str):
    y, _ = librosa.load(audio_file_path, sr=SR)

    # Nonequispaced Fast Fourier Transform (nFFT) para obtener el espectograma
    D = librosa.stft(y, n_fft=N_FFT, hop_length=HOP)
    spectrogram = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    return spectrogram

# Solo por si las moscas... por si se quiere ver el espectograma de la cancion
def show_spectrogram(spectrogram):
    plt.figure(figsize=(10, 4))
    librosa.display.specshow(spectrogram, sr=SR, x_axis="time", y_axis="log")
    plt.colorbar(format="%+2.0f dB")
    plt.title("Log-frequency spectrogram")
    plt.tight_layout()
    plt.show()