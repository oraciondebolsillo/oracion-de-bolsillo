"""Reels 720p con voz y texto sincronizado con los tiempos reales de síntesis."""
import asyncio
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from componer import fondo, lora, poppins
from .editorial import guion, titulo

ANCHO, ALTO = 720, 1280


def puntuar(palabras, texto):
    """Edge entrega palabras sin signos. Recupera los signos del guion original."""
    cursor = 0
    for palabra in palabras:
        coincidencia = re.search(r"(?<!\w)" + re.escape(palabra["texto"]) + r"(?!\w)", texto[cursor:], re.I)
        if coincidencia is None:
            continue
        inicio = cursor + coincidencia.start()
        fin = cursor + coincidencia.end()
        while fin < len(texto) and texto[fin] in ".,;:!?…»”)]":
            fin += 1
        if inicio > cursor and texto[inicio - 1] in "¿¡«“(":
            inicio -= 1
        palabra["texto"] = texto[inicio:fin]
        cursor = fin
    return palabras


async def sintetizar(texto, destino, cfg):
    import edge_tts

    voz = edge_tts.Communicate(
        texto, cfg.get("voz", "es-MX-DaliaNeural"),
        rate=cfg.get("velocidad_voz", "+4%"), boundary="WordBoundary",
    )
    palabras = []
    with open(destino, "wb") as audio:
        async for evento in voz.stream():
            if evento["type"] == "audio":
                audio.write(evento["data"])
            elif evento["type"] == "WordBoundary":
                palabras.append({"texto": evento["text"], "inicio": evento["offset"] / 1e7,
                                 "fin": (evento["offset"] + evento["duration"]) / 1e7})
    if not palabras or Path(destino).stat().st_size == 0:
        raise RuntimeError("La voz no devolvió audio y tiempos válidos")
    return puntuar(palabras, texto)


def bloques(palabras):
    resultado, actual = [], []
    for palabra in palabras:
        actual.append(palabra)
        if len(actual) >= 7 or palabra["texto"].endswith((".", "?", "!", ";")):
            resultado.append(actual)
            actual = []
    if actual:
        resultado.append(actual)
    return resultado


def lineas(texto, fuente, ancho):
    resultado, actual = [], ""
    for palabra in texto.split():
        nueva = f"{actual} {palabra}".strip()
        if actual and fuente.getlength(nueva) > ancho:
            resultado.append(actual)
            actual = palabra
        else:
            actual = nueva
    return resultado + ([actual] if actual else [])


def centrar(dibujo, texto, y, fuente, color, ancho=540):
    renglones = lineas(texto, fuente, ancho)
    paso = int(fuente.size * 1.3)
    for numero, linea in enumerate(renglones):
        dibujo.text(((ANCHO - fuente.getlength(linea)) / 2, y + numero * paso),
                    linea, font=fuente, fill=color)


def tarjeta(item, texto, final=False, portada=False):
    # Mismo espacio seguro para miniaturas y controles superpuestos de Instagram.
    oscuro = item["tipo"] == "oracion"
    img = Image.new("RGB", (ANCHO, ALTO), (25, 36, 48)) if oscuro else fondo(ANCHO, ALTO)
    tinta = (250, 244, 231) if oscuro else (40, 31, 24)
    dorado = (223, 189, 128) if oscuro else (128, 84, 27)
    d = ImageDraw.Draw(img)
    d.line((90, 225, 600, 225), fill=dorado, width=3)
    centrar(d, "Oración de Bolsillo" if portada else titulo(item), 270, poppins(28), dorado)
    for tam in range(58, 31, -2):
        fuente = lora(tam)
        if len(lineas(texto, fuente, 520)) <= 5:
            break
    alto = len(lineas(texto, fuente, 520)) * int(tam * 1.3)
    centrar(d, texto, 630 - alto // 2, fuente, tinta, 520)
    pie = "Oración de Bolsillo"
    if portada:
        pie = "@oraciondebolsillo"
    elif final:
        pie = "Una oración para cada día"
    centrar(d, pie, 950, poppins(26), dorado)
    if final:
        centrar(d, "Síguenos · @oraciondebolsillo", 1010, poppins(24), tinta)
    return img


def crear(item, destino, exe, musica, cfg, carpeta):
    carpeta = Path(carpeta)
    voz = carpeta / "voz.mp3"
    palabras = asyncio.run(asyncio.wait_for(sintetizar(guion(item), voz, cfg), timeout=120))
    # Decodificar a PCM para medir duración real, incluida la cola del último sonido.
    pcm = subprocess.run([exe, "-nostdin", "-v", "error", "-i", str(voz), "-f", "s16le", "-ac", "1",
                          "-ar", "24000", "-"], check=True, capture_output=True, timeout=60).stdout
    duracion_voz = len(pcm) / 48000
    if duracion_voz <= 0 or duracion_voz > cfg.get("duracion_maxima", 90):
        raise RuntimeError(f"Duración de voz fuera de límites: {duracion_voz:.1f}s")
    duracion = duracion_voz + 1.8
    grupos = bloques(palabras)
    lista = []
    for i, grupo in enumerate(grupos):
        texto = " ".join(p["texto"] for p in grupo)
        tarjeta(item, texto).save(carpeta / f"cuadro_{i}.png")
        inicio = 0 if i == 0 else grupo[0]["inicio"]
        fin = grupos[i + 1][0]["inicio"] if i + 1 < len(grupos) else duracion_voz
        if fin <= inicio:
            raise RuntimeError("La síntesis devolvió tiempos de voz desordenados")
        lista.extend([f"file 'cuadro_{i}.png'", f"duration {fin - inicio:.6f}"])
    tarjeta(item, "Que esta oración te acompañe hoy.", final=True).save(carpeta / "final.png")
    lista.extend(["file 'final.png'", "duration 1.8", "file 'final.png'"])
    manifiesto = carpeta / "cuadros.txt"
    manifiesto.write_text("\n".join(lista) + "\n", encoding="utf-8")
    tarjeta(item, titulo(item), portada=True).save(destino.with_suffix(".jpg"), quality=95)
    cmd = [exe, "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifiesto), "-i", str(voz)]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", str(musica), "-filter_complex",
                f"[1:a]apad,volume=1[a];[2:a]volume=0.16,afade=t=out:st={max(0, duracion-1.5)}:d=1.5[b];[a][b]amix=inputs=2:duration=first:normalize=0[out]",
                "-map", "0:v", "-map", "[out]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a", "-af", "apad"]
    cmd += ["-t", str(duracion), "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destino)]
    subprocess.run(cmd, check=True, timeout=240)
    # El archivo de tiempos se guarda junto al reel para poder revisar la sincronía.
    destino.with_suffix(".tiempos.json").write_text(json.dumps({"voz_segundos": duracion_voz,
        "palabras": palabras}, ensure_ascii=False, indent=2), encoding="utf-8")
