"""Utilidades compartidas: rutas, lectura/escritura de datos y avisos para GitHub."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

CONFIG_POR_DEFECTO = {
    "cuenta": "@oraciondebolsillo",
    "publicar_como": "reel",          # "reel" o "imagen"
    "compartir_en_feed": True,
    "con_musica": True,
    "aprobar_automaticamente": True,  # False: lo nuevo queda como "borrador" hasta que lo apruebes
    "hashtags_max": 5,
    "modelo": "claude-sonnet-5-5",
    "pendientes_minimos_para_generar": 21,
    "minimo_aviso_por_turno": 3,
}


def cargar(nombre):
    with open(DATOS / nombre, encoding="utf-8") as f:
        return json.load(f)


def guardar(nombre, datos):
    destino = DATOS / nombre
    tmp = destino.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, destino)


def config():
    cfg = dict(CONFIG_POR_DEFECTO)
    try:
        cfg.update(cargar("config.json"))
    except FileNotFoundError:
        pass
    return cfg


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hoy():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def salida_github(clave, valor):
    ruta = os.environ.get("GITHUB_OUTPUT")
    if ruta:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{clave}={valor}\n")
    print(f"[salida] {clave}={valor}")


def aviso(msg):
    print(f"::warning::{msg}", flush=True)


def error(msg):
    print(f"::error::{msg}", flush=True)
