"""Repone las reservas por tipo con la API de Claude y las añade a la cola.

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

from . import editorial, validar
from .comun import aviso, cargar, config, error, guardar, hoy

CTA = {
    "versiculo": ["📖 Guárdalo para leerlo cuando más lo necesites.", "📖 Guarda este versículo y vuelve a él cuando dudes.", "📖 Guárdalo y compártelo con alguien que lo necesite."],
    "reflexion": ["💬 Compártelo con alguien que lo necesite hoy.", "💬 Envíaselo a alguien que hoy necesita ánimo.", "💬 Compártelo con quien está pasando por un momento difícil."],
    "oracion": ["Guarda esta oración para volver a ella.", "Compártela con alguien a quien quieras acompañar.", "Haz una pausa y reza estas palabras a tu ritmo."],
}
TEMAS_ORACION = ["la ansiedad y los pensamientos que no dejan dormir", "la familia", "el trabajo y la provisión del día a día", "la salud propia o de un ser querido",
                 "el cansancio y las ganas de rendirse", "el perdón (dar y recibir)", "la gratitud", "la soledad", "una decisión difícil",
                 "el duelo y la pérdida de alguien", "la espera de una respuesta", "los hijos", "empezar de nuevo", "la paz en el hogar"]

SISTEMA = """Eres el redactor de "Oración de Bolsillo", una cuenta de Instagram de fe y esperanza para público de toda Latinoamérica.
Tu voz: cercana, serena, humilde y compasiva. Hablas de tú (nunca "vos" ni "vosotros"). Acompañas a quien está cansado, con miedo o esperando; no sermoneas ni juzgas.
Terreno común: Dios, Jesús, la oración, la confianza, la esperanza. Nada que divida a católicos y evangélicos (sin Virgen, santos, doctrina, política).
Prohibido: prometer dinero, prosperidad, sanidades o milagros concretos; presionar ("comparte o no recibirás"); inventar citas bíblicas; escribir referencias bíblicas (como 23:1) en tus textos; usar "está escrito", "la Biblia dice" o similares.
Estilo: frases cortas con imágenes concretas y cotidianas, sin clichés gastados, sin repetir ideas ni arranques entre publicaciones.
Escribes para reels narrados. La primera frase debe reconocer una situación concreta: cuidar a todos, esperar una llamada, una casa vacía, preocuparse por los hijos. Evita introducciones, amenazas espirituales y promesas de viralidad.
Cada pieza incluye "gancho" (20-90 caracteres, se pronuncia al principio, sin emoji) y "portada" (10-45 caracteres, de 3 a 7 palabras, sin emoji). No repitas el gancho en el cuerpo.
Las reflexiones incluyen "narracion" (180-380 caracteres) con una situación, una idea que la desarrolle y un cierre cálido. La frase de portada no sustituye el desarrollo.
Hashtags: de 4 a 5 en minúscula, prioriza #dios #jesus #amen y una etiqueta relacionada con el mensaje. El sistema decide la prueba de #fyp. No afirmes que una etiqueta garantiza visitas.
Cada pieza incluye "cta" (20-120 caracteres): una única invitación concreta y ligada al tema. Por ejemplo, enviar la oración a quien está cuidando a un familiar, compartir la reflexión con alguien que empieza de nuevo o guardar el versículo para un momento difícil. Varía la acción y el destinatario; evita pedir tres acciones o exigir comentarios de Amén.
Respondes SIEMPRE con un único objeto JSON válido, sin texto antes ni después."""


def construir_prompt(faltan, candidatos, temas, recientes):
    ver = "\n".join(f'- id "{i}": {v["ref"]} — {v["texto"]}' for i, v in candidatos.items())
    rec = "\n".join(f"- {r}" for r in recientes[-30:]) or "(ninguna todavía)"
    temas_txt = "\n".join(f"{n + 1}. {t}" for n, t in enumerate(temas))
    return f"""Necesito estas piezas para la próxima semana. Cantidad exacta de cada tipo: versiculos={faltan['versiculos']}, reflexiones={faltan['reflexiones']}, oraciones={faltan['oraciones']}.

1) VERSÍCULOS (publicación de la mañana). Elige de esta lista (NO escribas el versículo, solo su id), todos distintos entre sí:
{ver}
Para cada uno: "id", "destacado" (el comienzo EXACTO del versículo, copiado tal cual y con su coma o punto y coma final si la hay, 3 a 12 palabras, que se verá en dorado), "parrafo1" (30-240 caracteres: un gancho humano que conecte el versículo con la vida real, empieza con 1 emoji), "parrafo2" (30-240 caracteres: una aplicación práctica y cálida, empieza con 1 emoji), "hashtags" (4 a 5, en español o con #fe).

2) REFLEXIONES (publicación de la tarde). Una frase que dé ánimo, original, sin citar la Biblia.
Para cada una: "frase" (30-140 caracteres), "destacado" (comienzo EXACTO de la frase, 1 a 8 palabras), "parrafo1" y "parrafo2" (30-240 caracteres cada uno, empiezan con 1 emoji), "hashtags" (4 a 5).

3) ORACIONES (publicación de la noche). Una por cada tema, en este orden:
{temas_txt}
Para cada una: "tema", "frase" (40-125 caracteres, la frase corta que aparece en la imagen, en primera persona, se dirige a Dios), "destacado" (comienzo EXACTO de la frase, 1 a 3 palabras, p. ej. "Señor,"), "oracion" (la oración completa, 350-500 caracteres, primera persona, concreta, termina exactamente con "En el nombre de Jesús, amén."), "parrafo1" (30-240 caracteres, empieza con 1 emoji: gancho para la descripción), "hashtags" (4 a 5).

Ya existen estas frases; no repitas ideas ni arranques:
{rec}

Formato de respuesta (solo JSON):
{{"versiculos":[{{"id":"","destacado":"","gancho":"","portada":"","parrafo1":"","parrafo2":"","hashtags":["#dios","#jesus","#amen","#fe"]}}],
 "reflexiones":[{{"frase":"","destacado":"","gancho":"","portada":"","narracion":"","parrafo1":"","parrafo2":"","hashtags":["#dios","#jesus","#amen","#fe"]}}],
 "oraciones":[{{"tema":"","frase":"","destacado":"","gancho":"","portada":"","oracion":"","parrafo1":"","hashtags":["#dios","#jesus","#amen","#fe"]}}]}}"""


def llamar_claude(prompt, cfg):
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise SystemExit("Falta el secreto ANTHROPIC_API_KEY")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    esquemas = {}
    for tipo, campos in {
        "versiculos": ("id", "destacado", "gancho", "portada", "parrafo1", "parrafo2"),
        "reflexiones": ("frase", "destacado", "gancho", "portada", "narracion", "parrafo1", "parrafo2"),
        "oraciones": ("tema", "frase", "destacado", "gancho", "portada", "oracion", "parrafo1"),
    }.items():
        propiedades = {campo: {"type": "string"} for campo in campos}
        propiedades["cta"] = {"type": "string"}
        propiedades["hashtags"] = {"type": "array", "items": {"type": "string"}}
        esquemas[tipo] = {"type": "array", "items": {"type": "object", "properties": propiedades,
                            "required": list(propiedades), "additionalProperties": False}}
    peticion = {
        "model": cfg["modelo"], "max_tokens": 12000, "system": SISTEMA,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": {
            "type": "object", "properties": esquemas, "required": list(esquemas), "additionalProperties": False}}},
    }
    if cfg["modelo"].startswith("claude-sonnet-5-5"):
        # Sonnet 5.5 razona por defecto. Sin herramientas, between_tools deja todo el presupuesto al JSON.
        peticion["thinking"] = {"type": "between_tools"}
        peticion["output_config"]["effort"] = "low"
    r = requests.post(
        f"{base}/v1/messages",
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=peticion,
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"La API de Claude respondió {r.status_code}: {r.text[:400]}")
    datos = r.json()
    if datos.get("stop_reason") == "max_tokens":
        raise ValueError("La respuesta de Claude quedó truncada por el límite de tokens")
    texto = "".join(b.get("text", "") for b in datos.get("content", []) if b.get("type") == "text")
    if not texto.strip():
        raise ValueError("Claude no devolvió un bloque de texto con el JSON")
    return texto


def extraer_json(texto):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.S)
    bruto = m.group(1) if m else texto[texto.find("{"): texto.rfind("}") + 1]
    return json.loads(bruto)


def con_emoji(parrafo, emoji):
    return parrafo if parrafo and not parrafo[0].isalnum() else f"{emoji} {parrafo}"


def marcar(frase, destacado):
    # Si justo después del destacado hay puntuación (, ; : . etc.), se queda dentro de lo destacado.
    fin = len(destacado)
    while fin < len(frase) and frase[fin] in ",;:.¡!¿?":
        fin += 1
    return f"**{frase[:fin]}**{frase[fin:]}"


def ensamblar(tipo, it, ident, v=None):
    """Convierte lo que devuelve la IA en una publicación completa de la cola."""
    cta = it.get("cta") or CTA[tipo][(ident // 3) % 3]
    base = {"id": ident, "turno": {"versiculo": "manana", "reflexion": "tarde", "oracion": "noche"}[tipo], "tipo": tipo,
            "hashtags": " ".join(it["hashtags"]), "estado": "pendiente", "creado": hoy(), "publicado": None, "intentos": 0}
    for campo in ("gancho", "portada", "narracion"):
        if it.get(campo):
            base[campo] = it[campo]
    if tipo == "versiculo":
        base.update(texto=marcar(v["texto"], it["destacado"]), referencia=v["ref"], id_versiculo=it["id"],
                    descripcion=f'{con_emoji(it["parrafo1"], "🙏")}\n\n{con_emoji(it["parrafo2"], "✨")}\n\n{cta}')
    elif tipo == "reflexion":
        base.update(texto=marcar(it["frase"], it["destacado"]), referencia="",
                    descripcion=f'{con_emoji(it["parrafo1"], "✨")}\n\n{con_emoji(it["parrafo2"], "🌱")}\n\n{cta}')
    else:
        base.update(texto=marcar(it["frase"], it["destacado"]), referencia="", oracion=it["oracion"], tema=it.get("tema", ""),
                    descripcion=f'{con_emoji(it["parrafo1"], "🕯️")}\n\n🙏 Oración completa:\n\n{it["oracion"]}\n\n{cta}')
    base["hashtags"] = " ".join(editorial.hashtags(base, config()))
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
    objetivos = cfg.get("publicaciones_por_semana", {"versiculos": 7, "reflexiones": 7, "oraciones": 7})
    tipos = {"versiculos": "versiculo", "reflexiones": "reflexion", "oraciones": "oracion"}
    semanas = max(1, int(cfg.get("semanas_reserva", 2)))
    necesarios = {k: n if forzar else max(0, n * semanas - sum(c["tipo"] == tipos[k] for c in pendientes))
                  for k, n in objetivos.items()}
    if not any(necesarios.values()):
        print(f"Hay al menos {semanas} semana(s) de contenido pendiente por cada tipo.")
        return 0

    candidatos = candidatos_versiculos(cola, banco, cuantos=max(12, necesarios["versiculos"]))
    if len(candidatos) < necesarios["versiculos"]:
        raise SystemExit("No hay suficientes versículos verificados para esta tanda.")
    n_oraciones = sum(1 for c in cola if c.get("tipo") == "oracion")
    temas = [TEMAS_ORACION[(n_oraciones + i) % len(TEMAS_ORACION)] for i in range(necesarios["oraciones"])]
    previos = [validar.plano(c["texto"]) for c in cola] + [c.get("oracion", "") for c in cola if c.get("oracion")]

    buenos = {"versiculos": [], "reflexiones": [], "oraciones": []}
    usados_ids = set()
    rondas_necesarias = (max(necesarios.values()) + 2) // 3
    for intento in range(1, rondas_necesarias + intentos_max):
        faltan = {k: min(3, necesarios[k] - len(v)) for k, v in buenos.items()}
        if not any(faltan.values()):
            break
        libres = {i: v for i, v in candidatos.items() if i not in usados_ids}
        print(f"Intento {intento}: pido {faltan}")
        try:
            inicio_temas = len(buenos["oraciones"])
            temas_lote = temas[inicio_temas:inicio_temas + faltan["oraciones"]]
            datos = extraer_json(llamar_claude(construir_prompt(faltan, libres, temas_lote, previos), cfg))
            if not isinstance(datos, dict):
                raise ValueError("La respuesta debe ser un objeto JSON")
            for clave in buenos:
                if not isinstance(datos.get(clave, []), list) or any(not isinstance(it, dict) for it in datos.get(clave, [])):
                    raise ValueError(f"La lista {clave} tiene formato incorrecto")
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

    if any(len(v) < necesarios[k] for k, v in buenos.items()):
        error("No he conseguido toda la tanda válida; no se ha añadido nada a la cola.")
        return 1

    siguiente = max([c["id"] for c in cola] + [0]) + 1
    estado = "pendiente" if cfg["aprobar_automaticamente"] else "borrador"
    nuevas = []
    for d in range(max(necesarios.values())):
        for tipo, clave in (("versiculo", "versiculos"), ("reflexion", "reflexiones"), ("oracion", "oraciones")):
            if d >= len(buenos[clave]):
                continue
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
