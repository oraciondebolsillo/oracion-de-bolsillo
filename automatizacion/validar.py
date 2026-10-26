"""Reglas de calidad y seguridad para todo lo que escribe la IA.
Si algo no pasa, se descarta y se vuelve a pedir: nunca llega a publicarse."""
import difflib
import re
import unicodedata

# Temas y fórmulas que no queremos en la cuenta (promesas, prosperidad, divisiones entre iglesias...)
PROHIBIDAS = [
    "virgen", "santa maria", "rosario", "san jose", "santos", "purgatorio",
    "rico", "ricos", "riqueza", "riquezas", "prosperidad", "millonario", "abundancia financiera", "multiplica tu",
    "garantizado", "milagro garantizado", "te garantizo", "seguro que recibiras",
    "comparte y recibiras", "comparte para recibir", "si no compartes", "si compartes",
    "maldicion", "castigo de dios", "iras al infierno", "infierno",
    "politic", "elecciones", "vacuna", "cura del cancer", "curara tu",
]
# Frases que simulan una cita bíblica dentro de texto libre (el error típico de las cuentas con IA)
CITAS_FALSAS = [
    "esta escrito", "la biblia dice", "dice la biblia", "dijo jesus", "dice el senor", "asi dice",
    "dice dios:", "como dice la palabra", "la palabra dice", "el salmista",
]
RE_REFERENCIA = re.compile(r"\b\d{1,3}\s?:\s?\d{1,3}\b")
RE_HASHTAG = re.compile(r"^#[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9_]{2,30}$")
UMBRAL_REPETICION = 0.78


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def plano(t):
    return t.replace("**", "")


def _palabras_prohibidas(texto):
    n = " " + norm(texto) + " "
    return [p for p in PROHIBIDAS if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", n)]


def _citas_falsas(texto):
    n = norm(texto)
    return [c for c in CITAS_FALSAS if c in n]


def revisar_texto_libre(campos):
    """campos: dict nombre->texto. Devuelve lista de problemas."""
    problemas = []
    for nombre, t in campos.items():
        if not isinstance(t, str) or not t.strip():
            problemas.append(f"{nombre}: vacío")
            continue
        if "**" in t:
            problemas.append(f"{nombre}: no debe llevar ** (lo añade el sistema)")
        if "http" in t.lower() or "www." in t.lower() or "@" in t:
            problemas.append(f"{nombre}: no debe llevar enlaces ni @")
        if RE_REFERENCIA.search(t):
            problemas.append(f"{nombre}: contiene una referencia bíblica (capítulo:versículo)")
        for c in _citas_falsas(t):
            problemas.append(f"{nombre}: parece una cita bíblica inventada ('{c}')")
        for p in _palabras_prohibidas(t):
            problemas.append(f"{nombre}: contiene un tema no permitido ('{p}')")
    return problemas


def revisar_destacado(frase, destacado, max_palabras=12):
    if not isinstance(destacado, str) or not destacado.strip():
        return ["destacado: vacío"]
    if not frase.startswith(destacado):
        return ["destacado: debe ser el comienzo EXACTO de la frase"]
    if len(destacado) >= len(frase):
        return ["destacado: debe dejar parte de la frase sin destacar"]
    if len(destacado.split()) > max_palabras:
        return [f"destacado: máximo {max_palabras} palabras"]
    # Solo es un error cortar una palabra por la mitad. Si el destacado termina justo
    # antes de una coma, un punto y coma, etc. (la IA a veces los omite), es válido.
    if frase[len(destacado)].isalnum() and destacado[-1].isalnum():
        return ["destacado: debe terminar al final de una palabra"]
    return []


def revisar_hashtags(h):
    if not isinstance(h, list) or not (4 <= len(h) <= 7):
        return ["hashtags: deben ser entre 4 y 7"]
    malos = [x for x in h if not isinstance(x, str) or not RE_HASHTAG.match(x)]
    return [f"hashtags: formato incorrecto {malos}"] if malos else []


def revisar_longitud(nombre, t, minimo, maximo):
    if not isinstance(t, str):
        return [f"{nombre}: falta"]
    return [] if minimo <= len(t) <= maximo else [f"{nombre}: {len(t)} caracteres (debe tener entre {minimo} y {maximo})"]


def parecido(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def es_repetido(texto, previos):
    """True si se parece demasiado a algo ya escrito o publicado."""
    for p in previos:
        if parecido(texto, p) >= UMBRAL_REPETICION:
            return True
    return False


# ---------- una validación por tipo de publicación ----------
def validar_versiculo(it, candidatos):
    """candidatos: dict id -> {'ref','texto'}. Devuelve (problemas, versiculo_o_None)."""
    p = []
    v = candidatos.get(it.get("id"))
    if not v:
        return [f"id de versículo no permitido: {it.get('id')}"], None
    p += revisar_destacado(v["texto"], it.get("destacado", ""), 14)
    p += revisar_longitud("parrafo1", it.get("parrafo1"), 30, 240)
    p += revisar_longitud("parrafo2", it.get("parrafo2"), 30, 240)
    p += revisar_texto_libre({"parrafo1": it.get("parrafo1"), "parrafo2": it.get("parrafo2")})
    p += revisar_hashtags(it.get("hashtags"))
    return p, v


def validar_reflexion(it):
    p = []
    p += revisar_longitud("frase", it.get("frase"), 30, 140)
    p += revisar_texto_libre({"frase": it.get("frase"), "parrafo1": it.get("parrafo1"), "parrafo2": it.get("parrafo2")})
    if isinstance(it.get("frase"), str):
        p += revisar_destacado(it["frase"], it.get("destacado", ""), 10)
    p += revisar_longitud("parrafo1", it.get("parrafo1"), 30, 240)
    p += revisar_longitud("parrafo2", it.get("parrafo2"), 30, 240)
    p += revisar_hashtags(it.get("hashtags"))
    return p


def validar_oracion(it):
    p = []
    p += revisar_longitud("frase", it.get("frase"), 40, 125)
    p += revisar_longitud("oracion", it.get("oracion"), 350, 900)
    p += revisar_longitud("parrafo1", it.get("parrafo1"), 30, 240)
    p += revisar_texto_libre({"frase": it.get("frase"), "oracion": it.get("oracion"), "parrafo1": it.get("parrafo1")})
    if isinstance(it.get("frase"), str):
        p += revisar_destacado(it["frase"], it.get("destacado", ""), 6)
    if isinstance(it.get("oracion"), str) and not norm(it["oracion"]).endswith("amen."):
        p.append("oracion: debe terminar en 'amén.'")
    p += revisar_hashtags(it.get("hashtags"))
    return p
