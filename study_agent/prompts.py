"""Prompts y esquemas JSON de cada etapa del flujo.

Flujo: leer contenido -> clasificar tema -> extraer conceptos -> resumen
       -> preguntas tipo examen -> flashcards -> mapa conceptual

Se agrupan en 3 llamadas para ahorrar cuota de la suscripción:
  1) analizar   = clasificar + extraer conceptos
  2) estudiar   = resumen + mapa conceptual
  3) practicar  = preguntas tipo examen + flashcards
"""
from __future__ import annotations

import yaml

# Súbelo al cambiar prompts o esquemas para invalidar la caché de .cache/
PROMPT_VERSION = 2

SYSTEM = (
    "Eres un tutor experto en certificaciones de Microsoft Azure y en técnicas de estudio "
    "(recuperación activa, repetición espaciada). Trabajas SOLO con el contenido que se te da "
    "y con conocimiento oficial de Microsoft; no inventes servicios ni funcionalidades. "
    "Escribe en español neutro. Conserva en inglés los nombres de productos y términos que "
    "Microsoft usa en el examen (p. ej. Microsoft Foundry, Content Understanding, prompt, token), "
    "indicando la traducción entre paréntesis la primera vez si ayuda. "
    "Responde exclusivamente con un objeto JSON que cumpla el esquema pedido."
)


def exam_outline(exam: dict) -> str:
    return yaml.safe_dump(
        {"examen": exam["code"], "dominios": exam["domains"]}, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------- 1) analizar
ANALYZE_SCHEMA = {
    "type": "object",
    "properties": {
        "dominio_id": {"type": "string"},
        "habilidad_id": {"type": "string"},
        "habilidades_secundarias": {"type": "array", "items": {"type": "string"}},
        "justificacion": {"type": "string"},
        "relevancia_examen": {"type": "string", "enum": ["alta", "media", "baja"]},
        "conceptos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "definicion": {"type": "string"},
                    "importancia": {"type": "string", "enum": ["alta", "media", "baja"]},
                    "relacionados": {"type": "array", "items": {"type": "string"}},
                    "trampa_examen": {"type": "string"},
                },
                "required": ["nombre", "definicion", "importancia", "relacionados"],
            },
        },
    },
    "required": ["dominio_id", "habilidad_id", "justificacion", "relevancia_examen", "conceptos"],
}


def analyze_prompt(exam: dict, title: str, content: str) -> str:
    return f"""Tarea: CLASIFICAR el tema y EXTRAER CONCEPTOS del siguiente módulo de Microsoft Learn.

Temario oficial del examen (usa exactamente estos id):
{exam_outline(exam)}

Instrucciones:
- dominio_id / habilidad_id: la habilidad del temario que MEJOR cubre este módulo.
- habilidades_secundarias: otros habilidad_id que el módulo también toca.
- conceptos: entre 8 y 18 conceptos evaluables (términos, servicios, técnicas, principios).
  * nombre: corto y canónico, como título de nota de Obsidian (sin ":" "/" "#" ni corchetes).
    Usa el nombre que Microsoft usa en el examen. Singular. Ej.: "Retrieval Augmented Generation (RAG)".
  * definicion: 1-2 frases, precisa, en tus palabras.
  * relacionados: nombres de OTROS conceptos de esta misma lista.
  * trampa_examen: confusión típica o distractor probable en el examen (vacío si no aplica).

Módulo: {title}
--- CONTENIDO ---
{content}
--- FIN ---"""


# ---------------------------------------------------------------- 2) estudiar
STUDY_SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "puntos_clave": {"type": "array", "items": {"type": "string"}},
        "mapa": {
            "type": "object",
            "properties": {
                "central": {"type": "string"},
                "nodos": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "etiqueta": {"type": "string"}},
                    "required": ["id", "etiqueta"]}},
                "relaciones": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"desde": {"type": "string"}, "hasta": {"type": "string"},
                                   "etiqueta": {"type": "string"}},
                    "required": ["desde", "hasta", "etiqueta"]}},
            },
            "required": ["central", "nodos", "relaciones"],
        },
    },
    "required": ["resumen", "puntos_clave", "mapa"],
}


def study_prompt(title: str, content: str, concepts: list[dict]) -> str:
    names = "\n".join(f"- {c['nombre']}" for c in concepts)
    return f"""Tarea: elabora un RESUMEN de estudio y un MAPA CONCEPTUAL del módulo.

Resumen (campo "resumen", Markdown):
- 250-450 palabras, orientado al examen: qué es, para qué sirve, cuándo usar cada opción.
- Usa subtítulos ### y listas. Cuando nombres un concepto de la lista, escríbelo EXACTO
  entre dobles corchetes para enlazarlo en Obsidian: [[Nombre exacto]] (solo la primera vez).
- No copies párrafos del original: reformula.

puntos_clave: 5-8 frases cortas que DEBES recordar para el examen.

Mapa conceptual (campo "mapa"):
- central: tema central del módulo.
- nodos: 8-16 nodos; usa los nombres EXACTOS de la lista de conceptos como etiqueta cuando
  correspondan. id = identificador corto sin espacios (a-z, 0-9, _). Incluye un nodo con
  id "central".
- relaciones: aristas con verbo/frase de enlace corta ("es un tipo de", "usa", "se evalúa con",
  "produce", "mitiga"...). Forma una jerarquía legible desde "central"; evita cruces innecesarios.

Conceptos extraídos:
{names}

Módulo: {title}
--- CONTENIDO ---
{content}
--- FIN ---"""


# ---------------------------------------------------------------- 3) practicar
PRACTICE_SCHEMA = {
    "type": "object",
    "properties": {
        "preguntas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["opcion_unica", "opcion_multiple", "si_no", "escenario"]},
                "enunciado": {"type": "string"},
                "opciones": {"type": "array", "items": {"type": "string"}},
                "correctas": {"type": "array", "items": {"type": "integer"}},
                "afirmaciones": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"texto": {"type": "string"}, "verdadera": {"type": "boolean"}},
                    "required": ["texto", "verdadera"]}},
                "explicacion": {"type": "string"},
                "concepto": {"type": "string"},
            },
            "required": ["tipo", "enunciado", "explicacion", "concepto"],
        }},
        "flashcards": {"type": "array", "items": {
            "type": "object",
            "properties": {"frente": {"type": "string"}, "reverso": {"type": "string"}},
            "required": ["frente", "reverso"]}},
    },
    "required": ["preguntas", "flashcards"],
}


def practice_prompt(exam: dict, title: str, content: str, concepts: list[dict],
                    n_questions: int, n_cards: int) -> str:
    concept_lines = "\n".join(
        f"- {c['nombre']}: {c['definicion']}" + (f" | Trampa: {c['trampa_examen']}" if c.get("trampa_examen") else "")
        for c in concepts)
    return f"""Tarea: genera PREGUNTAS TIPO EXAMEN {exam['code']} y FLASHCARDS del módulo.

Preguntas ({n_questions}), con el estilo real de los exámenes de Microsoft:
- Mezcla tipos:
  * "opcion_unica": 4 opciones, 1 correcta.
  * "opcion_multiple": 4-5 opciones, 2-3 correctas; el enunciado indica cuántas elegir.
  * "si_no": 3 afirmaciones en "afirmaciones" (cada una verdadera/falsa); "opciones" y "correctas" vacíos.
  * "escenario": caso de negocio breve ("Una empresa necesita...") con 4 opciones, 1 correcta.
- "correctas" = índices base 0 dentro de "opciones".
- Distractores plausibles: servicios o conceptos reales que se confunden (usa las trampas).
- "explicacion": por qué la correcta lo es y por qué las otras no (2-4 frases).
- "concepto": nombre EXACTO del concepto evaluado (de la lista).
- Prioriza lo que el temario evalúa; dificultad nivel Fundamentals, sin trivialidades.

Flashcards ({n_cards}) para repetición espaciada:
- Una sola idea por tarjeta (principio de información mínima).
- frente: pregunta concreta (qué/cuándo/cuál/diferencia). reverso: respuesta breve (máx. ~25 palabras).
- Incluye tarjetas de "¿Qué servicio usarías para...?" y de diferencias entre conceptos parecidos.
- Sin saltos de línea, sin "::" ni "?" sueltos en una línea.

Conceptos:
{concept_lines}

Módulo: {title}
--- CONTENIDO ---
{content}
--- FIN ---"""
