# Azure Study Agent

Convierte rutas, módulos o unidades de **Microsoft Learn** en notas de estudio para **Obsidian**,
usando **Claude Code con tu suscripción de Claude** (sin API key).

📖 **[Manual de uso completo](docs/MANUAL.md)**: instalación, comandos, cómo estudiar con las notas,
configuración, temarios propios y solución de problemas.

```
URL de Learn → leer contenido → clasificar tema (temario oficial) → extraer conceptos
            → resumen → preguntas tipo examen → flashcards → mapa conceptual → Obsidian
```

## Instalación

`study-agent` es un binario autocontenido: **no necesitas Python**. Funciona en macOS (Intel y
Apple Silicon), Linux (x64 y arm64) y Windows (x64).

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.sh | sh
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.ps1 | iex
```

El instalador descarga el binario de tu plataforma desde
[GitHub Releases](https://github.com/byrogr/azure-study-agent/releases), verifica su SHA-256
y lo deja en el PATH (`~/.local/bin` o `%LOCALAPPDATA%\Programs\study-agent`). Para una versión
concreta: `STUDY_AGENT_VERSION=v0.1.0` (o `$env:STUDY_AGENT_VERSION` en PowerShell).
Para actualizar, vuelve a ejecutar el instalador.

**Requisito: Claude Code** con tu cuenta Pro/Max (study-agent lo usa para generar las notas):
```bash
curl -fsSL https://claude.ai/install.sh | bash      # macOS / Linux
irm https://claude.ai/install.ps1 | iex             # Windows
claude                                              # inicia sesión con "Claude account", luego /exit
```

**Primer uso**
```bash
study-agent init        # te pide la carpeta de tu vault de Obsidian
```

En Obsidian instala el plugin comunitario **Spaced Repetition** (flashcards). Mermaid ya viene incluido.

<details>
<summary>Otras formas de instalar</summary>

- **Con Python (pipx o uv):** `pipx install git+https://github.com/byrogr/azure-study-agent`
  o `uv tool install git+https://github.com/byrogr/azure-study-agent`.
- **Manual:** descarga el binario de tu plataforma en Releases, dale permisos de ejecución
  (`chmod +x`) y ponlo en una carpeta del PATH.
- **Docker:** ver más abajo.

**Desinstalar:** borra el binario (`rm ~/.local/bin/study-agent` o la carpeta
`%LOCALAPPDATA%\Programs\study-agent`) y, si quieres, `~/.config/study-agent` y `~/.cache/study-agent`
(en Windows `%APPDATA%\study-agent` y `%LOCALAPPDATA%\study-agent`).
</details>

### Desarrollo

```bash
git clone https://github.com/byrogr/azure-study-agent && cd azure-study-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                       # `study-agent` usa el código del repo
python -m unittest discover tests
```

## Con Docker (sin instalar Python ni Node)

Solo necesitas [Docker Desktop](https://www.docker.com/products/docker-desktop/) y una cuenta de Claude Pro/Max.

```bash
# 1. Construye la imagen y genera el token de tu suscripción (una vez)
docker build -t azure-study-agent .
docker run --rm -it --entrypoint claude azure-study-agent setup-token

# 2. Configura .env con tu vault y el token
cp .env.example .env      # edita VAULT_DIR y CLAUDE_CODE_OAUTH_TOKEN

# 3. Usa el agente con los mismos subcomandos que en local
docker compose run --rm study-agent list https://learn.microsoft.com/es-es/training/paths/ai-concepts/
docker compose run --rm study-agent generate https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --only 1
```

- El vault se monta en `/vault`; la caché de etapas vive en el volumen `study-agent-cache`.
- Para cambiar la configuración (modelo, nº de preguntas...), monta tu archivo:
  descomenta la línea de `config.yaml` en `volumes` de `docker-compose.yml`
  (`vault_path` se ignora en Docker: manda `VAULT_DIR`).
- `.env` contiene tu token: no lo subas a git (ya está en `.gitignore`).

## Uso

```bash
study-agent list <url>          # qué módulos/unidades leerá, sin gastar uso de Claude
study-agent generate <url>      # genera las notas en tu vault
study-agent exams               # temarios disponibles
study-agent init                # (re)crea la configuración
study-agent --help              # ayuda; también `study-agent generate --help`
```

La URL puede ser una ruta, un módulo o una unidad de Learn:

```bash
study-agent generate https://learn.microsoft.com/es-es/training/paths/ai-concepts/
study-agent generate https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --only 1 2
study-agent generate https://learn.microsoft.com/es-es/training/modules/rag-fundamentals/
study-agent generate https://learn.microsoft.com/es-es/training/modules/get-started-ai-fundamentals/7-responsible-ai

# Opciones de generate
--model opus      # más calidad (consume más cuota); haiku = más rápido
--exam ai-200     # otro temario (ver "Configuración y temarios")
--force           # regenera ignorando la caché
```

Las URLs en inglés se reescriben al idioma de `learn_locale` (por defecto `es-es`).

## Configuración y temarios

| Qué | Dónde |
| --- | --- |
| Configuración | `~/.config/study-agent/config.yaml` · Windows: `%APPDATA%\study-agent\config.yaml` (la crea `study-agent init`; plantilla en `study_agent/config.example.yaml`) |
| Temarios propios | `<carpeta de config>/exams/<id>.yaml` (mismo formato que `study_agent/exams/ai-901.yaml`; pisan a los incluidos) |
| Caché de etapas | `~/.cache/study-agent/` · Windows: `%LOCALAPPDATA%\study-agent\cache` |

Variables de entorno: `STUDY_AGENT_CONFIG` (archivo de config), `STUDY_AGENT_CONFIG_DIR`,
`STUDY_AGENT_VAULT` (sustituye a `vault_path`), `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`.
También puedes pasar `-c RUTA` a cualquier comando.

## Qué genera en tu vault

```
Certificaciones/AI-901/
├── AI-901 - Mapa de estudio.md      índice por dominio y habilidad del temario, con progreso
├── Módulos/<módulo>.md              puntos clave, resumen, conceptos, mapa Mermaid,
│                                    preguntas (respuesta plegable) y flashcards
├── Conceptos/<concepto>.md          una nota por concepto, con trampas de examen y backlinks
└── .study-agent/index.json          índice interno
```

- **Clasificación:** cada módulo se asigna a un dominio y habilidad de `study_agent/exams/ai-901.yaml`
  (temario oficial del 15-abr-2026) y se etiqueta `#ai-901/<dominio>`, `#ai-901/<habilidad>`.
- **Preguntas:** opción única, selección múltiple, Sí/No y escenarios, con explicación.
- **Flashcards:** formato `pregunta::respuesta` del plugin Spaced Repetition, mazo
  `#flashcards/ai-901/<módulo>`.
- **Mapa conceptual:** `flowchart` Mermaid; los nodos que son conceptos son clicables y abren su nota.

## Cómo usa tu suscripción

Cada módulo hace 3 llamadas a `claude -p` (clasificar+conceptos, resumen+mapa,
preguntas+flashcards) con salida JSON validada por esquema, sin herramientas y sin cargar
configuración de ningún proyecto. Consume tu límite de uso como cualquier sesión de Claude Code.
Si se corta a mitad, vuelve a ejecutar: las etapas terminadas quedan en `~/.cache/study-agent/`.

## Estructura del código

| Archivo | Responsabilidad |
| --- | --- |
| `study_agent/cli.py` | Comando `study-agent` y sus subcomandos |
| `study_agent/paths.py` | Rutas de configuración, caché y temarios |
| `study_agent/learn.py` | Descubre módulos/unidades y lee el Markdown oficial (`?accept=text/markdown`) |
| `study_agent/prompts.py` | Prompts y esquemas JSON de cada etapa |
| `study_agent/llm.py` | Wrapper de `claude -p` con reintentos |
| `study_agent/pipeline.py` | Orquestación y caché por etapa |
| `study_agent/obsidian.py` | Notas, conceptos, Mermaid y mapa de estudio |
| `study_agent/exams/*.yaml` | Temario de cada certificación |
| `tests/run_offline.py` | Prueba end-to-end con contenido local |
| `tests/test_units.py` | Tests unitarios offline: `python -m unittest discover tests` |
| `Dockerfile`, `docker-compose.yml` | Imagen con Python + Claude Code CLI |
| `install.sh`, `install.ps1` | Instaladores de una línea (descargan el binario de Releases) |
| `packaging/entry.py` | Punto de entrada del binario autocontenido (PyInstaller) |
| `.github/workflows/` | `ci.yml`: tests en Linux/macOS/Windows · `release.yml`: binarios y release al subir un tag `v*` |

## Publicar una versión

```bash
# 1. Sube la versión en study_agent/__init__.py (p. ej. "0.2.0") y haz commit
git tag v0.2.0 && git push origin main v0.2.0
```

El workflow `Release` compila los 5 binarios, los prueba y crea la release con sus checksums;
desde ese momento los instaladores descargan esa versión.

## Licencia

[MIT](LICENSE)
