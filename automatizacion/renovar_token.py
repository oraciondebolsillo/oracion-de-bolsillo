"""Renueva el token de Instagram (dura 60 días; se renueva cada 2 semanas para que no caduque nunca).

  python -m automatizacion.renovar_token nuevo_token.txt   (necesita la variable IG_TOKEN)
"""
import os
import sys

import requests

from .comun import aviso, error

IG_BASE = os.environ.get("IG_API_BASE", "https://graph.instagram.com")


def renovar(token):
    r = requests.get(f"{IG_BASE}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    if r.status_code != 200:
        return None, r.text[:300]
    d = r.json()
    return d["access_token"], d.get("expires_in")


if __name__ == "__main__":
    token = os.environ.get("IG_TOKEN")
    if not token or len(sys.argv) < 2:
        error("Uso: IG_TOKEN=... python -m automatizacion.renovar_token archivo_salida")
        sys.exit(1)
    nuevo, info = renovar(token)
    if nuevo is None:
        if any(x in str(info).lower() for x in ("24 hours", "not old enough", "too new")):
            aviso("El token es demasiado reciente para renovarlo (hay que esperar 24 h). Se renovará en la próxima ejecución.")
            sys.exit(0)
        error(f"No se pudo renovar el token: {info}. Si ya caducó, genera uno nuevo en el panel de Meta y actualiza el secreto IG_TOKEN.")
        sys.exit(1)
    print(f"::add-mask::{nuevo}")
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write(nuevo)
    print(f"Token renovado: válido durante {int(info) // 86400} días más.")
