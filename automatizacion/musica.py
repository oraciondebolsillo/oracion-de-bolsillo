"""Música ambiental sencilla y 100% original, generada por el propio sistema (sin derechos de autor).

Si pones archivos de audio (mp3/wav/m4a) en la carpeta "musica", se usan esos en su lugar.
Un pad suave de acordes + notas sueltas tipo caja de música, con algo de reverberación."""
import wave
from pathlib import Path

import numpy as np

SR = 44100
DURACION = 7.0

# Dos acordes por reel (notas MIDI). Cada serie suena distinta; se elige según el número de publicación.
PROGRESIONES = [
    ([48, 55, 60, 64, 67], [45, 52, 60, 64, 69]),   # Do -> La menor
    ([41, 48, 57, 60, 65], [48, 55, 60, 64, 67]),   # Fa -> Do
    ([50, 57, 62, 66, 69], [47, 54, 59, 62, 66]),   # Re -> Si menor
    ([43, 50, 59, 62, 67], [40, 47, 55, 59, 64]),   # Sol -> Mi menor
    ([45, 52, 57, 60, 64], [41, 48, 57, 60, 65]),   # La menor -> Fa
]


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _envolvente(t, t0, t1, ataque, relajo):
    e = np.clip((t - t0) / ataque, 0, 1) * np.clip(1 - (t - t1) / relajo, 0, 1)
    return e * e * (3 - 2 * e)  # curva suave


def sintetizar(semilla):
    rnd = np.random.default_rng(semilla)
    t = np.arange(int(SR * DURACION)) / SR
    izq, der = np.zeros_like(t), np.zeros_like(t)
    acordes = PROGRESIONES[semilla % len(PROGRESIONES)]
    limites = [(0.0, 3.9), (3.3, 7.4)]
    for notas, (t0, t1) in zip(acordes, limites):
        env = _envolvente(t, t0, t1, 1.1, 1.4)
        for m in notas:
            f = _hz(m)
            fase = rnd.uniform(0, 2 * np.pi, 2)
            base_l = np.sin(2 * np.pi * f * 0.998 * t + fase[0]) + 0.35 * np.sin(2 * np.pi * 2 * f * t + fase[1]) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
            base_r = np.sin(2 * np.pi * f * 1.002 * t + fase[1]) + 0.35 * np.sin(2 * np.pi * 2 * f * 1.001 * t + fase[0]) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
            peso = 1.0 / (1 + (m - 40) / 24)  # más suave en los agudos
            izq += env * base_l * peso
            der += env * base_r * peso
    izq, der = izq / 9.0, der / 9.0

    # notas sueltas (caja de música): arpegio sobre las notas del acorde en una octava superior
    for k in range(8):
        inicio = 0.45 + k * 0.82
        notas = acordes[0 if inicio < 3.5 else 1]
        m = notas[(k * 2 + semilla) % len(notas)] + 12
        f = _hz(m)
        dt = np.clip(t - inicio, 0, None)
        golpe = (t >= inicio) * np.exp(-dt / 0.75) * np.clip(dt / 0.01, 0, 1)
        tono = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2.01 * f * t) * np.exp(-dt / 0.25)
        voz = 0.16 * golpe * tono
        pan = 0.3 + 0.4 * (k % 2)
        izq += voz * (1 - pan)
        der += voz * pan

    # reverberación suave: respuesta de ruido que decae
    n = int(SR * 1.6)
    ir = rnd.standard_normal((2, n)) * np.exp(-np.arange(n) / (SR * 0.45))
    salida = []
    for canal, resp in ((izq, ir[0]), (der, ir[1])):
        largo = len(canal) + n
        cola = np.fft.irfft(np.fft.rfft(canal, largo) * np.fft.rfft(resp, largo), largo)[: len(canal)]
        cola /= max(1e-9, np.max(np.abs(cola)))
        salida.append(canal * 0.78 + cola * 0.22 * np.max(np.abs(canal)))
    st = np.stack(salida, axis=1)

    # volumen de fondo (≈ -20 dB RMS) sin pasar de -3 dB de pico
    rms = np.sqrt(np.mean(st ** 2))
    st *= 10 ** (-20 / 20) / max(rms, 1e-9)
    pico = np.max(np.abs(st))
    if pico > 0.7:
        st *= 0.7 / pico
    return st


def guardar_wav(st, destino):
    datos = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(datos.tobytes())


def audio_para(numero, carpeta_trabajo, carpeta_musica):
    """Devuelve la ruta del audio a usar para la publicación `numero`."""
    propios = sorted(p for p in Path(carpeta_musica).glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
    if propios:
        return propios[numero % len(propios)]
    destino = Path(carpeta_trabajo) / f"musica_{numero}.wav"
    guardar_wav(sintetizar(numero), destino)
    return destino
