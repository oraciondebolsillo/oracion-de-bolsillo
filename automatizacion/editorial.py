"""Criterios comunes para publicaciones nuevas y contenido antiguo de la cola."""
import re
import unicodedata


def limpiar(texto):
    texto = texto.replace("**", "")
    return re.sub(r"\s+", " ", "".join(
        c for c in texto if unicodedata.category(c)[0] in "LNPZ"
    )).strip()


def hashtags(item, cfg):
    """Etiquetas amplias de fe y una prueba configurable de descubrimiento."""
    base = cfg.get("hashtags_base", ["#dios", "#jesus", "#amen"])
    contexto = limpiar(item.get("tema") or item.get("texto", "")).lower()
    tematicas = (
        (("hijo", "familia", "hogar", "casa"), "#familia"),
        (("miedo", "ansiedad", "dormir", "paz", "descans"), "#paz"),
        (("gracias", "gratitud", "agrade"), "#gratitud"),
        (("perdon", "perdón"), "#perdon"),
    )
    tema = next((tag for palabras, tag in tematicas if any(p in contexto for p in palabras)), "#fe")
    prueba = cfg.get("hashtag_descubrimiento", "#fyp")
    ultima = prueba if prueba and int(item["id"]) % 2 == 0 else "#oracion"
    resultado = []
    for tag in [*base, tema, ultima]:
        tag = unicodedata.normalize("NFC", tag.strip().lower())
        if re.fullmatch(r"#[\w]{2,30}", tag) and tag not in resultado:
            resultado.append(tag)
    return resultado[:min(5, max(0, int(cfg.get("hashtags_max", 5))))]


def guion(item):
    """Incluye el contenido completo en la narración, también en colas antiguas."""
    frase = limpiar(item["texto"])
    gancho = limpiar(item.get("gancho", ""))
    if not gancho and item["tipo"] == "oracion":
        primer_parrafo = limpiar(item.get("descripcion", "").split("\n")[0])
        primera_frase = re.split(r"(?<=[.!?])\s+", primer_parrafo)[0]
        if 20 <= len(primera_frase) <= 110 and primera_frase != frase:
            gancho = primera_frase
    if item["tipo"] == "oracion":
        cuerpo = limpiar(item.get("oracion") or frase)
    elif item["tipo"] == "reflexion":
        parrafos = item.get("descripcion", "").split("\n\n")
        aplicacion = limpiar(parrafos[1]) if len(parrafos) > 1 else ""
        cuerpo = limpiar(item.get("narracion") or f"{frase} {aplicacion}")
    else:
        cuerpo = f'{frase} {item.get("referencia", "")}.'.strip()
    return " ".join(t for t in (gancho, cuerpo) if t)


def titulo(item):
    if not item.get("portada") and not item.get("gancho"):
        contexto = limpiar(item.get("tema") or item.get("texto", "")).lower()
        for palabras, portada in (
            (("ansiedad", "miedo"), "Cuando la mente no descansa"),
            (("cansancio", "rendir"), "Para quien está agotado"),
            (("hijo", "familia"), "Una oración por tu familia"),
            (("soledad", "solo"), "Para cuando te sientes solo"),
            (("perdón", "perdon"), "Cuando cuesta perdonar"),
            (("gratitud", "gracias"), "Gracias por lo sencillo"),
            (("espera", "respuesta"), "Mientras llega esa respuesta"),
            (("salud", "enfer"), "Por quien necesita fuerzas"),
            (("trabajo", "provisión"), "Por el trabajo de mañana"),
            (("decisión", "decidir"), "Cuando no sabes qué decidir"),
            (("duelo", "pérdida"), "Para cuando extrañas a alguien"),
            (("empezar", "nuevo"), "Dios te acompaña al empezar"),
            (("hogar", "paz en"), "Una oración por tu hogar"),
        ):
            if any(p in contexto for p in palabras):
                return portada
    return limpiar(item.get("portada") or item.get("gancho") or {
        "oracion": "Una oración para hoy",
        "reflexion": "Fe para este momento",
        "versiculo": "Una palabra para hoy",
    }[item["tipo"]])
