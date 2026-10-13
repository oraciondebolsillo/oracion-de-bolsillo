"""
Oración de Bolsillo - Compositor de publicaciones
-------------------------------------------------
Lee publicaciones.json y crea en la carpeta "salida", para cada publicación:
  - NN_dia_turno.jpg  -> imagen para publicación normal (1080x1350)
  - NN_dia_turno.mp4  -> vídeo vertical para reel (1080x1920, 7 s, sin música)
  - NN_dia_turno.txt  -> descripción y hashtags para copiar y pegar
Todas llevan el mismo fondo y diseño.
"""
import json
import random
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("Falta la librería Pillow. Ejecuta: pip install pillow")
    sys.exit(1)

BASE = Path(__file__).resolve().parent
FUENTES = BASE / "fuentes"
SALIDA = BASE / "salida"

ANCHO = 1080
ALTO_POST, ALTO_REEL = 1350, 1920
MARGEN = 110
MARFIL = (244, 238, 227)
TINTA = (40, 31, 24)
DORADO = (166, 120, 52)
GRIS = (128, 112, 96)
MARCA = "Oración de Bolsillo"

SEGUNDOS_REEL = 7
FPS = 30
ZOOM_FINAL = 1.04


# ---------- fuentes ----------
def lora(tamano, negrita=False, cursiva=False, peso=None):
    archivo = "Lora-Italic-Variable.ttf" if cursiva else "Lora-Variable.ttf"
    f = ImageFont.truetype(str(FUENTES / archivo), tamano)
    try:
        f.set_variation_by_axes([peso or (700 if negrita else 400)])
    except Exception:
        pass
    return f


def poppins(tamano, peso="Medium"):
    return ImageFont.truetype(str(FUENTES / f"Poppins-{peso}.ttf"), tamano)


# ---------- fondo fijo (igual en todas) ----------
_fondos = {}


def fondo(ancho, alto):
    if (ancho, alto) in _fondos:
        return _fondos[(ancho, alto)].copy()
    rnd = random.Random(7)  # semilla fija: siempre el mismo fondo
    img = Image.new("RGB", (ancho, alto), MARFIL)

    luz = Image.new("L", (ancho, alto), 0)
    d = ImageDraw.Draw(luz)
    cx, cy = ancho // 2, int(alto * 0.36)
    radio = max(ancho, alto) * 1.05
    for r in range(int(radio), 0, -6):
        v = int(255 * (1 - r / radio) ** 1.8)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=v)
    img = Image.composite(Image.new("RGB", (ancho, alto), (252, 248, 240)), img, luz)
    sombra = Image.eval(luz, lambda v: int(max(0, 150 - v) * 0.35))
    img = Image.composite(Image.new("RGB", (ancho, alto), (214, 200, 178)), img, sombra)

    grano = Image.effect_noise((ancho, alto), 22).filter(ImageFilter.GaussianBlur(0.6))
    grano = Image.eval(grano, lambda v: int(abs(v - 128) * 0.55))
    img = Image.composite(Image.new("RGB", (ancho, alto), (205, 190, 166)), img, grano)
    fibras = Image.new("L", (ancho, alto), 0)
    df = ImageDraw.Draw(fibras)
    for _ in range(int(260 * alto / ALTO_POST)):
        x, y = rnd.randint(0, ancho), rnd.randint(0, alto)
        largo = rnd.randint(8, 40)
        df.line([(x, y), (x + largo, y + rnd.randint(-3, 3))], fill=rnd.randint(10, 26), width=1)
    img = Image.composite(Image.new("RGB", (ancho, alto), (190, 170, 140)), img, fibras.filter(ImageFilter.GaussianBlur(0.5)))
    _fondos[(ancho, alto)] = img
    return img.copy()


# ---------- texto ----------
def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def trozos(texto):
    """'**destacado** normal' -> lista de (palabra, destacada). Lo destacado va en cursiva dorada."""
    salida = []
    for i, parte in enumerate(re.split(r"\*\*", texto)):
        for palabra in parte.split():
            salida.append((palabra, i % 2 == 1))
    return salida


def maquetar(palabras, tam, ancho_max):
    f_n, f_d = lora(tam), lora(tam, cursiva=True, peso=500)
    espacio = f_n.getlength(" ")
    lineas, actual, ancho = [], [], 0
    for palabra, dest in palabras:
        w = (f_d if dest else f_n).getlength(palabra)
        extra = w if not actual else espacio + w
        if actual and ancho + extra > ancho_max:
            lineas.append((actual, ancho))
            actual, ancho = [(palabra, dest, w)], w
        else:
            actual.append((palabra, dest, w))
            ancho += extra
    if actual:
        lineas.append((actual, ancho))
    return lineas, f_n, f_d, espacio


def texto_espaciado(dib, xy, texto, fuente, color, espaciado):
    anchos = [fuente.getlength(c) for c in texto]
    total = sum(anchos) + espaciado * (len(texto) - 1)
    x, y = xy[0] - total / 2, xy[1]
    for c, w in zip(texto, anchos):
        dib.text((x, y), c, font=fuente, fill=color)
        x += w + espaciado
    return total


def cruz(dib, cx, cy, alto, color, grosor=4):
    dib.rectangle([cx - grosor / 2, cy - alto / 2, cx + grosor / 2, cy + alto / 2], fill=color)
    brazo = alto * 0.34
    yb = cy - alto * 0.18
    dib.rectangle([cx - brazo, yb - grosor / 2, cx + brazo, yb + grosor / 2], fill=color)


def adorno(dib, cx, y):
    dib.line([(cx - 120, y), (cx - 26, y)], fill=DORADO, width=2)
    dib.line([(cx + 26, y), (cx + 120, y)], fill=DORADO, width=2)
    cruz(dib, cx, y, 36, DORADO, 4)


def componer(pub, alto=ALTO_POST):
    """Publicación 1080x1350. En el reel (1080x1920) es exactamente el mismo diseño,
    centrado en vertical, para que todo quede siempre a la misma altura."""
    img = fondo(ANCHO, alto)
    dib = ImageDraw.Draw(img)
    oy = (alto - ALTO_POST) // 2
    palabras = trozos(pub["texto"])

    for tam in range(78, 35, -2):
        lineas, f_n, f_d, espacio = maquetar(palabras, tam, ANCHO - 2 * MARGEN)
        alto_linea = int(tam * 1.34)
        if len(lineas) * alto_linea <= 640:
            break

    ref = pub.get("referencia")
    oracion = bool(pub.get("oracion"))
    alto_bloque = 70 + len(lineas) * alto_linea + (70 if ref else 0) + (90 if oracion else 0)
    zona_arriba, zona_abajo = 90, ALTO_POST - 170
    y = oy + zona_arriba + (zona_abajo - zona_arriba - alto_bloque) // 2
    cx = ANCHO // 2

    adorno(dib, cx, y + 10)
    y += 70
    for linea, ancho in lineas:
        x = cx - ancho / 2
        for palabra, dest, w in linea:
            dib.text((x, y), palabra, font=f_d if dest else f_n, fill=DORADO if dest else TINTA)
            x += w + espacio
        y += alto_linea
    if ref:
        y += 26
        texto_espaciado(dib, (cx, y), f"{ref} · RVR1960".upper(), poppins(26, "Medium"), DORADO, 5)
        y += 44
    if oracion:
        y += 40
        texto_espaciado(dib, (cx, y), "ORACIÓN COMPLETA EN LA DESCRIPCIÓN", poppins(21, "Medium"), DORADO, 3)
        yf = y + 44
        dib.line([(cx - 12, yf), (cx, yf + 10), (cx + 12, yf)], fill=DORADO, width=3, joint="curve")

    # firma: siempre en la misma posición
    yb = oy + ALTO_POST - 118
    f_marca = lora(38, cursiva=True)
    w = f_marca.getlength(MARCA)
    dib.text((cx - w / 2, yb), MARCA, font=f_marca, fill=TINTA)
    dib.line([(cx - 60, yb + 62), (cx + 60, yb + 62)], fill=DORADO, width=2)
    return img


# ---------- vídeo para reels ----------
def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def hacer_reel(img, destino, exe, audio=None):
    """Crea el vídeo del reel. Si se pasa un archivo de audio, lo incorpora (AAC)."""
    w, h = img.size
    frames = SEGUNDOS_REEL * FPS
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a",
                "-af", f"afade=t=in:d=0.4,afade=t=out:st={SEGUNDOS_REEL - 1.2}:d=1.2",
                "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", str(SEGUNDOS_REEL)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        z = 1 + (ZOOM_FINAL - 1) * (i / (frames - 1))
        cw, ch = w / z, h / z
        x0, y0 = (w - cw) / 2, (h - ch) / 2
        cuadro = img.resize((w, h), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        proc.stdin.write(cuadro.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg no pudo crear el vídeo")


# ---------- foto de perfil ----------
def foto_perfil():
    tam = 1080
    img = fondo(tam, tam)
    dib = ImageDraw.Draw(img)
    c = tam // 2
    dib.ellipse([c - 430, c - 430, c + 430, c + 430], outline=DORADO, width=8)
    dib.ellipse([c - 400, c - 400, c + 400, c + 400], outline=DORADO, width=3)
    f = lora(600, negrita=True)
    caja = dib.textbbox((0, 0), "O", font=f)
    ow, oh = caja[2] - caja[0], caja[3] - caja[1]
    dib.text((c - ow / 2 - caja[0], c - oh / 2 - caja[1]), "O", font=f, fill=TINTA)
    cruz(dib, c, c + 8, 230, DORADO, 20)
    return img


def main():
    datos = json.loads((BASE / "publicaciones.json").read_text(encoding="utf-8"))
    SALIDA.mkdir(exist_ok=True)
    exe = ffmpeg()
    if not exe:
        print("Aviso: no encuentro ffmpeg; solo se crearán las imágenes (ejecuta: pip install imageio-ffmpeg).")
    for p in datos["publicaciones"]:
        nombre = sin_tildes(f"{p['id']:02d}_{p['dia']}_{p['turno']}".lower())
        componer(p).save(SALIDA / f"{nombre}.jpg", quality=95)
        (SALIDA / f"{nombre}.txt").write_text(f"{p['descripcion']}\n\n{p['hashtags']}\n", encoding="utf-8")
        if exe:
            hacer_reel(componer(p, ALTO_REEL), SALIDA / f"{nombre}.mp4", exe)
        print(f"  {nombre}")
    foto_perfil().save(SALIDA / "00_foto_de_perfil.png")
    print(f"\nListo: {len(datos['publicaciones'])} publicaciones en la carpeta 'salida'.")


if __name__ == "__main__":
    main()
