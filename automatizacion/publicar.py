"""Prepara (imagen/vídeo) y publica en Instagram la siguiente publicación pendiente de un turno.

  python -m automatizacion.publicar preparar --turno manana --salida sitio
  python -m automatizacion.publicar publicar --turno manana --url-base https://usuario.github.io/repo [--simulacro]
"""
import argparse
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests

from . import musica, validar
from .comun import RAIZ, aviso, cargar, config, error, guardar, ahora, salida_github

TURNOS = ("manana", "tarde", "noche")
IG_BASE = os.environ.get("IG_API_BASE", "https://graph.instagram.com")
IG_VERSION = os.environ.get("IG_API_VERSION", "v25.0")
ESPERA = float(os.environ.get("IG_POLL_SEGUNDOS", "20"))          # segundos entre comprobaciones
MAX_ESPERA = float(os.environ.get("IG_MAX_ESPERA", "900"))         # máximo esperando a Instagram / a la web
MAX_INTENTOS = 3


class ErrorIG(Exception):
    pass


# ---------- cola ----------
def pendientes_turno(cola, turno):
    return sorted((c for c in cola if c.get("estado") == "pendiente" and c.get("turno") == turno), key=lambda c: c["id"])


def siguiente(cola, turno):
    p = pendientes_turno(cola, turno)
    return p[0] if p else None


def caption(item, cfg):
    tags = item["hashtags"].split()[: cfg["hashtags_max"]]
    cierre = (cfg.get("cierre_descripcion") or {}).get(item.get("tipo"), "").strip()
    cuerpo = f'{item["descripcion"]}\n\n{cierre}' if cierre else item["descripcion"]
    texto = f'{cuerpo}\n\n{" ".join(tags)}'
    if len(texto) > 2200:
        raise ErrorIG(f"La descripción de la publicación {item['id']} supera los 2200 caracteres de Instagram")
    return texto


def nombre_archivo(item, cfg):
    return f'{item["id"]}.{"mp4" if cfg["publicar_como"] == "reel" else "jpg"}'


# ---------- preparar ----------
def preparar(turno, salida):
    from componer import ALTO_POST, ALTO_REEL, componer, ffmpeg, hacer_reel

    cfg, cola = config(), cargar("cola.json")
    item = siguiente(cola, turno)
    if not item:
        error(f"No quedan publicaciones pendientes para el turno '{turno}'. Revisa que funcione el workflow 'Generar semana'.")
        return 1
    quedan = len(pendientes_turno(cola, turno))
    if quedan <= cfg["minimo_aviso_por_turno"]:
        aviso(f"Quedan solo {quedan} publicaciones para el turno '{turno}'.")

    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    pub = {"texto": item["texto"], "referencia": item.get("referencia", ""), "oracion": item.get("oracion")}
    destino = salida / nombre_archivo(item, cfg)
    if cfg["publicar_como"] == "reel":
        exe = ffmpeg()
        if not exe:
            error("No encuentro ffmpeg")
            return 1
        audio = None
        with tempfile.TemporaryDirectory() as tmp:
            if cfg["con_musica"]:
                audio = musica.audio_para(item["id"], tmp, RAIZ / "musica")
            hacer_reel(componer(pub, ALTO_REEL), destino, exe, audio)
    else:
        componer(pub, ALTO_POST).save(destino, quality=95)
    if not destino.exists() or destino.stat().st_size < 20_000:
        error("El archivo generado está vacío o es demasiado pequeño")
        return 1
    (salida / "index.html").write_text("<!doctype html><meta charset=utf-8><title>Oración de Bolsillo</title><p>Oración de Bolsillo</p>", encoding="utf-8")
    print(f"Preparada la publicación {item['id']} ({item['tipo']}, turno {turno}): {destino.name} {destino.stat().st_size // 1024} KB")
    salida_github("id", item["id"])
    salida_github("archivo", destino.name)
    return 0


# ---------- Instagram ----------
def api(metodo, ruta, token, **kw):
    url = f"{IG_BASE}/{IG_VERSION}/{ruta}"
    r = requests.request(metodo, url, headers={"Authorization": f"Bearer {token}"}, timeout=120, **kw)
    if r.status_code >= 400:
        try:
            e = r.json().get("error", {})
        except ValueError:
            e = {}
        msg = e.get("message") or r.text[:300]
        if e.get("code") == 190 or r.status_code == 401:
            msg = f"El token de Instagram no es válido o ha caducado. Genera uno nuevo y actualiza el secreto IG_TOKEN. ({msg})"
        raise ErrorIG(f"Instagram respondió {r.status_code} en {metodo} {ruta}: {msg}")
    return r.json()


def esperar_url(url):
    """Espera a que GitHub Pages sirva ya el archivo (tarda unos segundos tras desplegar)."""
    fin = time.time() + MAX_ESPERA
    ultimo = ""
    while time.time() < fin:
        try:
            r = requests.get(url, stream=True, timeout=30)
            largo = int(r.headers.get("Content-Length") or 0)
            r.close()
            if r.status_code == 200 and largo > 20_000:
                print(f"Archivo disponible en {url} ({largo // 1024} KB)")
                return
            ultimo = f"estado {r.status_code}, tamaño {largo}"
        except requests.RequestException as e:
            ultimo = str(e)[:100]
        time.sleep(min(10, ESPERA))
    raise ErrorIG(f"El archivo no está accesible en {url} ({ultimo})")


def ya_publicado(uid, token, texto):
    """Seguro anti-duplicados: ¿ya hay una publicación reciente con esta misma descripción?"""
    try:
        datos = api("GET", f"{uid}/media", token, params={"fields": "caption,timestamp", "limit": 12})
    except ErrorIG as e:
        aviso(f"No pude comprobar duplicados: {e}")
        return False
    clave = validar.norm(texto)[:80]
    return any(validar.norm(m.get("caption") or "")[:80] == clave for m in datos.get("data", []))


def publicar_en_instagram(uid, token, item, url, cfg):
    cuerpo = {"caption": caption(item, cfg)}
    if cfg["publicar_como"] == "reel":
        cuerpo.update(media_type="REELS", video_url=url, share_to_feed=bool(cfg["compartir_en_feed"]))
    else:
        cuerpo.update(image_url=url)
    cid = api("POST", f"{uid}/media", token, json=cuerpo)["id"]
    print(f"Contenedor creado: {cid}")
    fin = time.time() + MAX_ESPERA
    while True:
        estado = api("GET", cid, token, params={"fields": "status_code,status"})
        codigo = estado.get("status_code")
        print(f"  estado del contenedor: {codigo}")
        if codigo == "FINISHED":
            break
        if codigo in ("ERROR", "EXPIRED"):
            raise ErrorIG(f"Instagram no pudo procesar el archivo: {estado.get('status') or codigo}")
        if time.time() > fin:
            raise ErrorIG("Instagram tardó demasiado en procesar el archivo")
        time.sleep(ESPERA)
    return api("POST", f"{uid}/media_publish", token, json={"creation_id": cid})["id"]


def publicar(turno, url_base, simulacro):
    cfg, cola = config(), cargar("cola.json")
    token = os.environ.get("IG_TOKEN")
    if not token:
        error("Falta el secreto IG_TOKEN")
        return 1
    me = api("GET", "me", token, params={"fields": "user_id,username"})
    uid = me.get("user_id") or me.get("id")
    print(f"Conectado a Instagram como @{me.get('username')} (id {uid})")

    item = siguiente(cola, turno)
    if not item:
        error(f"No quedan publicaciones pendientes para el turno '{turno}'")
        return 1
    url = f"{url_base.rstrip('/')}/{nombre_archivo(item, cfg)}"
    esperar_url(url)
    if simulacro:
        print(f"SIMULACRO correcto: la conexión funciona y se publicaría la nº {item['id']} ({item['tipo']}). No se ha publicado nada.")
        return 0

    texto = caption(item, cfg)
    if ya_publicado(uid, token, texto):
        aviso(f"La publicación {item['id']} ya estaba en Instagram; la marco como publicada sin repetirla.")
        item.update(estado="publicado", publicado={"fecha": ahora(), "ig_media_id": None, "nota": "ya existía"})
        guardar("cola.json", cola)
        return 0
    try:
        media_id = publicar_en_instagram(uid, token, item, url, cfg)
    except Exception as e:
        item["intentos"] = item.get("intentos", 0) + 1
        item["ultimo_error"] = str(e)[:300]
        if item["intentos"] >= MAX_INTENTOS:
            item["estado"] = "error"
            error(f"La publicación {item['id']} ha fallado {MAX_INTENTOS} veces y se aparta de la cola.")
        guardar("cola.json", cola)
        error(str(e))
        return 1
    item.update(estado="publicado", publicado={"fecha": ahora(), "ig_media_id": media_id})
    item.pop("ultimo_error", None)
    guardar("cola.json", cola)  # se guarda ya, antes de cualquier otra cosa
    try:
        item["publicado"]["enlace"] = api("GET", media_id, token, params={"fields": "permalink"}).get("permalink")
        guardar("cola.json", cola)
    except ErrorIG:
        pass
    print(f"PUBLICADA la nº {item['id']} ({item['tipo']}): {item['publicado'].get('enlace') or media_id}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("preparar")
    a.add_argument("--turno", required=True, choices=TURNOS)
    a.add_argument("--salida", default="sitio")
    b = sub.add_parser("publicar")
    b.add_argument("--turno", required=True, choices=TURNOS)
    b.add_argument("--url-base", required=True)
    b.add_argument("--simulacro", action="store_true")
    args = ap.parse_args()
    if args.cmd == "preparar":
        sys.exit(preparar(args.turno, args.salida))
    sys.exit(publicar(args.turno, args.url_base, args.simulacro))
