"""Escribe la semana siguiente (21 publicaciones) con la API de Claude y la añade a la cola.

Reglas de oro:
  * El texto de los versículos lo copia el código desde datos/banco_versiculos.json (nunca la IA).
  * Todo lo que escribe la IA pasa por validar.py; lo que no pasa se descarta y se vuelve a pedir.
"""
import argparse
import json
import os
import re
import sys

import requests

from . import validar
from .comun import aviso, cargar, config, error, guardar, hoy

CTA = {
    "versiculo": ["📖 Guárdalo para leerlo cuando más lo necesites.", "📖 Guarda este versículo y vuelve a él cuando dudes.", "📖 Guárdalo y compártelo con alguien que lo necesite."],
    "reflexion": ["💬 Compártelo con alguien que lo necesite hoy.", "💬 Envíaselo a alguien que hoy necesita ánimo.", "💬 Compártelo con quien está pasando por un momento difícil."],
    "oracion": ["Si esta oración es para ti, escribe Amén.", "Si la haces tuya, escribe Amén.", "Si la sientes tuya, escribe Amén."],
}
TEMAS_ORACION = ["la ansiedad y los pensamientos que no dejan dormir", "la familia", "el trabajo y la provisión del día a día", "la salud propia o de un ser querido",
                 "el cansancio y las ganas de rendirse", "el perdón (dar y recibir)", "la gratitud", "la soledad", "una decisión difícil",
                 "el duelo y la pérdida de alguien", "la espera de una respuesta", "los hijos", "empezar de nuevo", "la paz en el hogar"]

SISTEMA = """Eres el redactor de "Oración de Bolsillo", una cuenta de Instagram de fe y esperanza para público de toda Latinoamérica.
Tu voz: cercana, serena, humilde y compasiva. Hablas de tú (nunca "vos" ni "vosotros"). Acompañas a quien está cansado, con miedo o esperando; no sermoneas ni juzgas.
Terreno común: Dios, Jesús, la oración, la confianza, la esperanza. Nada que divida a católicos y evangélicos (sin Virgen, santos, doctrina, política).
Prohibido: prometer dinero, prosperidad, sanidades o milagros concretos; presionar ("comparte o no recibirás"); inventar citas bíblicas; escribir referencias bíblicas (como 23:1) en tus textos; usar "está escrito", "la Biblia dice" o similares.
Estilo: frases cortas con imágenes concretas y cotidianas, sin clichés gastados, sin repetir ideas ni arranques entre publicaciones.
Respondes SIEMPRE con un único objeto JSON válido, sin texto antes ni después."""


def construir_prompt(faltan, candidatos, temas, recientes):
    ver = "\n".join(f'- id "{i}": {v["ref"]} — {v["texto"]}' for i, v in candidatos.items())
    rec = "\n".join(f"- {r}" for r in recientes[-30:]) or "(ninguna todavía)"
    temas_txt = "\n".join(f"{n + 1}. {t}" for n, t in enumerate(temas))
    return f"""Necesito estas piezas para la próxima semana. Cantidad exacta de cada tipo: versiculos={faltan['versiculos']}, reflexiones={faltan['reflexiones']}, oraciones={faltan['oraciones']}.

1) VERSÍCULOS (publicación de la mañana). Elige de esta lista (NO escribas el versículo, solo su id), todos distintos entre sí:
{ver}
Para cada uno: "id", "destacado" (el comienzo EXACTO del versículo, copiado tal cual, 3 a 12 palabras, que se verá en dorado), "parrafo1" (30-240 caracteres: un gancho humano que conecte el versículo con la vida real, empieza con 1 emoji), "parrafo2" (30-240 caracteres: una aplicación práctica y cálida, empieza con 1 emoji), "hashtags" (4 a 6, en español o con #fe).

2) REFLEXIONES (publicación de la tarde). Una frase que dé ánimo, original, sin citar la Biblia.
Para cada una: "frase" (30-140 caracteres), "destacado" (comienzo EXACTO de la frase, 1 a 8 palabras), "parrafo1" y "parrafo2" (30-240 caracteres cada uno, empiezan con 1 emoji), "hashtags" (4 a 6).

3) ORACIONES (publicación de la noche). Una por cada tema, en este orden:
{temas_txt}
Para cada una: "tema", "frase" (40-125 caracteres, la frase corta que aparece en la imagen, en primera persona, se dirige a Dios), "destacado" (comienzo EXACTO de la frase, 1 a 3 palabras, p. ej. "Señor,"), "oracion" (la oración completa, 350-800 caracteres, primera persona, concreta, termina exactamente con "En el nombre de Jesús, amén."), "parrafo1" (30-240 caracteres, empieza con 1 emoji: gancho para la descripción), "hashtags" (4 a 6).

Ya existen estas frases; no repitas ideas ni arranques:
{rec}

Formato de respuesta (solo JSON):
{{"versiculos":[{{"id":"","destacado":"","parrafo1":"","parrafo2":"","hashtags":["#fe"]}}],
 "reflexiones":[{{"frase":"","destacado":"","parrafo1":"","parrafo2":"","hashtags":["#fe"]}}],
 "oraciones":[{{"tema":"","frase":"","destacado":"","oracion":"","parrafo1":"","hashtags":["#fe"]}}]}}"""


def llamar_claude(prompt, cfg):
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise SystemExit("Falta el secreto ANTHROPIC_API_KEY")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    r = requests.post(
        f"{base}/v1/messages",
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": cfg["modelo"], "max_tokens": 16000, "system": SISTEMA, "messages": [{"role": "user", "content": prompt}]},
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"La API de Claude respondió {r.status_code}: {r.text[:400]}")
    datos = r.json()
    return "".join(b.get("text", "") for b in datos.get("content", []) if b.get("type") == "text")


def extraer_json(texto):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.S)
    bruto = m.group(1) if m else texto[texto.find("{"): texto.rfind("}") + 1]
    return json.loads(bruto)


def con_emoji(parrafo, emoji):
    return parrafo if parrafo and not parrafo[0].isalnum() else f"{emoji} {parrafo}"


def marcar(frase, destacado):
    return f"**{destacado}**{frase[len(destacado):]}"


def ensamblar(tipo, it, ident, v=None):
    """Convierte lo que devuelve la IA en una publicación completa de la cola."""
    cta = CTA[tipo][ident % 3]
    base = {"id": ident, "turno": {"versiculo": "manana", "reflexion": "tarde", "oracion": "noche"}[tipo], "tipo": tipo,
            "hashtags": " ".join(it["hashtags"]), "estado": "pendiente", "creado": hoy(), "publicado": None, "intentos": 0}
    if tipo == "versiculo":
        base.update(texto=marcar(v["texto"], it["destacado"]), referencia=v["ref"], id_versiculo=it["id"],
                    descripcion=f'{con_emoji(it["parrafo1"], "🙏")}\n\n{con_emoji(it["parrafo2"], "✨")}\n\n{cta}')
    elif tipo == "reflexion":
        base.update(texto=marcar(it["frase"], it["destacado"]), referencia="",
                    descripcion=f'{con_emoji(it["parrafo1"], "✨")}\n\n{con_emoji(it["parrafo2"], "🌱")}\n\n{cta}')
    else:
        base.update(texto=marcar(it["frase"], it["destacado"]), referencia="", oracion=it["oracion"], tema=it.get("tema", ""),
                    descripcion=f'{con_emoji(it["parrafo1"], "🕯️")}\n\n🙏 Oración completa:\n\n{it["oracion"]}\n\n{cta}')
    return base


def candidatos_versiculos(cola, banco, cuantos=12):
    por_ref = {v["ref"]: v["id"] for v in banco["versiculos"]}
    ultimo = {}
    for n, c in enumerate(cola):
        if c.get("tipo") == "versiculo" and c.get("referencia") in por_ref:
            ultimo[por_ref[c["referencia"]]] = n
    ver = [v for v in banco["versiculos"] if v.get("verificado")]
    ver.sort(key=lambda v: ultimo.get(v["id"], -1))
    return {v["id"]: v for v in ver[:cuantos]}


def generar(forzar=False, intentos_max=4):
    cfg = config()
    cola = cargar("cola.json")
    banco = cargar("banco_versiculos.json")
    pendientes = [c for c in cola if c.get("estado") == "pendiente"]
    if len(pendientes) > cfg["pendientes_minimos_para_generar"] and not forzar:
        print(f"Hay {len(pendientes)} publicaciones pendientes; no hace falta generar más todavía.")
        return 0

    candidatos = candidatos_versiculos(cola, banco)
    if len(candidatos) < 7:
        raise SystemExit("El banco tiene menos de 7 versículos verificados.")
    n_oraciones = sum(1 for c in cola if c.get("tipo") == "oracion")
    temas = [TEMAS_ORACION[(n_oraciones + i) % len(TEMAS_ORACION)] for i in range(7)]
    previos = [validar.plano(c["texto"]) for c in cola] + [c.get("oracion", "") for c in cola if c.get("oracion")]

    buenos = {"versiculos": [], "reflexiones": [], "oraciones": []}
    usados_ids = set()
    for intento in range(1, intentos_max + 1):
        faltan = {k: 7 - len(v) for k, v in buenos.items()}
        if not any(faltan.values()):
            break
        libres = {i: v for i, v in candidatos.items() if i not in usados_ids}
        print(f"Intento {intento}: pido {faltan}")
        try:
            datos = extraer_json(llamar_claude(construir_prompt(faltan, libres, temas[len(buenos['oraciones']):], previos), cfg))
        except (json.JSONDecodeError, ValueError) as e:
            aviso(f"Respuesta no válida (JSON): {e}")
            continue
        rechazos = []
        for it in datos.get("versiculos", [])[: faltan["versiculos"]]:
            p, v = validar.validar_versiculo(it, libres)
            if not p and it["id"] in usados_ids:
                p = ["versículo repetido en esta tanda"]
            if p:
                rechazos.append((it.get("id"), p))
            else:
                buenos["versiculos"].append((it, v))
                usados_ids.add(it["id"])
        for clave, funcion, campo in (("reflexiones", validar.validar_reflexion, "frase"), ("oraciones", validar.validar_oracion, "frase")):
            for it in datos.get(clave, [])[: faltan[clave]]:
                p = funcion(it)
                if not p:
                    textos = [it["frase"]] + ([it["oracion"]] if clave == "oraciones" else [])
                    if any(validar.es_repetido(t, previos) for t in textos):
                        p = ["demasiado parecida a otra ya escrita"]
                if p:
                    rechazos.append((str(it.get(campo))[:40], p))
                else:
                    buenos[clave].append((it, None))
                    previos += [it["frase"]] + ([it["oracion"]] if clave == "oraciones" else [])
        for quien, p in rechazos:
            print(f"  descartado ({quien}): {'; '.join(p)}")

    if any(len(v) < 7 for v in buenos.values()):
        error("No he conseguido 21 publicaciones válidas; no se ha añadido nada a la cola.")
        return 1

    siguiente = max([c["id"] for c in cola] + [0]) + 1
    estado = "pendiente" if cfg["aprobar_automaticamente"] else "borrador"
    nuevas = []
    for d in range(7):
        for tipo, clave in (("versiculo", "versiculos"), ("reflexion", "reflexiones"), ("oracion", "oraciones")):
            it, v = buenos[clave][d]
            pub = ensamblar(tipo, it, siguiente, v)
            pub["estado"] = estado
            nuevas.append(pub)
            siguiente += 1
    cola += nuevas
    guardar("cola.json", cola)
    print(f"Añadidas {len(nuevas)} publicaciones nuevas ({estado}). Total en cola: {len(cola)}.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="generar aunque queden publicaciones pendientes")
    sys.exit(generar(ap.parse_args().forzar))
