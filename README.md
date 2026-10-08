# Azure Study Agent

Convierte rutas, módulos o unidades de **Microsoft Learn** en notas de estudio para **Obsidian**,
usando **Claude Code con tu suscripción de Claude** (sin API key).

```
URL de Learn → leer contenido → clasificar tema (temario oficial) → extraer conceptos
            → resumen → preguntas tipo examen → flashcards → mapa conceptual → Obsidian
```

## Instalación (macOS)

```bash
# 1. Claude Code (si no lo tienes) e inicio de sesión con tu cuenta Pro/Max
npm install -g @anthropic-ai/claude-code
claude          # elige "Claude account" al iniciar sesión, luego /exit

# 2. El agente
cd azure-study-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # edita vault_path
```

En Obsidian instala el plugin comunitario **Spaced Repetition** (flashcards). Mermaid ya viene incluido.

## Con Docker (sin instalar Python ni Node)

Solo necesitas [Docker Desktop](https://www.docker.com/products/docker-desktop/) y una cuenta de Claude Pro/Max.

```bash
# 1. Construye la imagen y genera el token de tu suscripción (una vez)
docker build -t azure-study-agent .
docker run --rm -it --entrypoint claude azure-study-agent setup-token

# 2. Configura .env con tu vault y el token
cp .env.example .env      # edita VAULT_DIR y CLAUDE_CODE_OAUTH_TOKEN

# 3. Usa el agente igual que en local
docker compose run --rm study-agent https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --list
docker compose run --rm study-agent https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --only 1
```

- El vault se monta en `/vault`; la caché de etapas vive en el volumen `study-agent-cache`.
- Para cambiar la configuración (modelo, nº de preguntas...), monta tu archivo:
  añade `- ./config.yaml:/app/config.yaml:ro` en `volumes` de `docker-compose.yml`
  (`vault_path` se ignora en Docker: manda `VAULT_DIR`).
- `.env` contiene tu token: no lo subas a git (ya está en `.gitignore`).

## Uso

La URL se pasa como parámetro; acepta ruta, módulo o unidad:

```bash
# Ruta completa (procesa todos sus módulos)
python -m study_agent https://learn.microsoft.com/es-es/training/paths/ai-concepts/

# Ver qué módulos/unidades leerá, sin gastar uso de Claude
python -m study_agent https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --list

# Solo algunos módulos de la ruta (1-based)
python -m study_agent https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --only 1 2

# Un módulo o una unidad suelta
python -m study_agent https://learn.microsoft.com/es-es/training/modules/rag-fundamentals/
python -m study_agent https://learn.microsoft.com/es-es/training/modules/get-started-ai-fundamentals/7-responsible-ai

# Opciones útiles
--model opus      # más calidad (consume más cuota); haiku = más rápido
--exam ai-200     # otro examen (crea exams/ai-200.yaml con su temario)
--force           # regenera ignorando la caché
```

Las URLs en inglés se reescriben al idioma de `learn_locale` (por defecto `es-es`).

## Qué genera en tu vault

```
Certificaciones/AI-901/
├── AI-901 - Mapa de estudio.md      índice por dominio y habilidad del temario, con progreso
├── Módulos/<módulo>.md              puntos clave, resumen, conceptos, mapa Mermaid,
│                                    preguntas (respuesta plegable) y flashcards
├── Conceptos/<concepto>.md          una nota por concepto, con trampas de examen y backlinks
└── .study-agent/index.json          índice interno
```

- **Clasificación:** cada módulo se asigna a un dominio y habilidad de `exams/ai-901.yaml`
  (temario oficial del 15-abr-2026) y se etiqueta `#ai-901/<dominio>`, `#ai-901/<habilidad>`.
- **Preguntas:** opción única, selección múltiple, Sí/No y escenarios, con explicación.
- **Flashcards:** formato `pregunta::respuesta` del plugin Spaced Repetition, mazo
  `#flashcards/ai-901/<módulo>`.
- **Mapa conceptual:** `flowchart` Mermaid; los nodos que son conceptos son clicables y abren su nota.

## Cómo usa tu suscripción

Cada módulo hace 3 llamadas a `claude -p` (clasificar+conceptos, resumen+mapa,
preguntas+flashcards) con salida JSON validada por esquema, sin herramientas y sin cargar
configuración de ningún proyecto. Consume tu límite de uso como cualquier sesión de Claude Code.
Si se corta a mitad, vuelve a ejecutar: las etapas terminadas quedan en `.cache/`.

## Estructura del código

| Archivo | Responsabilidad |
| --- | --- |
| `study_agent/learn.py` | Descubre módulos/unidades y lee el Markdown oficial (`?accept=text/markdown`) |
| `study_agent/prompts.py` | Prompts y esquemas JSON de cada etapa |
| `study_agent/llm.py` | Wrapper de `claude -p` con reintentos |
| `study_agent/pipeline.py` | Orquestación y caché por etapa |
| `study_agent/obsidian.py` | Notas, conceptos, Mermaid y mapa de estudio |
| `exams/*.yaml` | Temario de cada certificación |
| `tests/run_offline.py` | Prueba end-to-end con contenido local |
| `tests/test_units.py` | Tests unitarios offline: `python -m unittest discover tests` |
| `Dockerfile`, `docker-compose.yml` | Imagen con Python + Claude Code CLI |

## Licencia

[MIT](LICENSE)
