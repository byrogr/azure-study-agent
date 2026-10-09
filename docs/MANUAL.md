# Manual de uso de study-agent

`study-agent` convierte el contenido de **Microsoft Learn** en un sistema de estudio dentro de
**Obsidian**: resúmenes, conceptos enlazados, mapas conceptuales, preguntas tipo examen y
flashcards con repetición espaciada, organizado según el temario oficial de la certificación.

Usa **Claude Code con tu suscripción de Claude** (Pro o Max), así que no necesitas API key ni
pagar por uso aparte.

---

## Índice

1. [Cómo funciona](#1-cómo-funciona)
2. [Requisitos](#2-requisitos)
3. [Instalación](#3-instalación)
4. [Primeros pasos (5 minutos)](#4-primeros-pasos-5-minutos)
5. [Comandos](#5-comandos)
6. [Qué se genera en Obsidian](#6-qué-se-genera-en-obsidian)
7. [Cómo estudiar con las notas](#7-cómo-estudiar-con-las-notas)
8. [Configuración](#8-configuración)
9. [Otros temarios y certificaciones](#9-otros-temarios-y-certificaciones)
10. [Consumo de tu suscripción y caché](#10-consumo-de-tu-suscripción-y-caché)
11. [Uso con Docker](#11-uso-con-docker)
12. [Actualizar y desinstalar](#12-actualizar-y-desinstalar)
13. [Solución de problemas](#13-solución-de-problemas)
14. [Preguntas frecuentes](#14-preguntas-frecuentes)

---

## 1. Cómo funciona

```
URL de Microsoft Learn
   │  1. Lee las unidades del módulo (Markdown oficial de Learn)
   ▼
Claude (vía Claude Code, 3 llamadas por módulo)
   │  2. Clasifica el módulo en el temario y extrae conceptos
   │  3. Escribe el resumen y el mapa conceptual
   │  4. Genera preguntas tipo examen y flashcards
   ▼
Tu vault de Obsidian
      Notas de módulo · notas de concepto · mapa de estudio con tu progreso
```

Le das una URL de Learn (una **ruta de aprendizaje**, un **módulo** o una **unidad**) y
`study-agent` hace el resto.

## 2. Requisitos

| Necesitas | Por qué |
| --- | --- |
| macOS, Linux o Windows (64 bits) | `study-agent` es un binario autocontenido; **no necesitas Python** |
| [Claude Code](https://claude.com/claude-code) con sesión iniciada | Es el motor que genera las notas |
| Suscripción **Claude Pro o Max** | Claude Code la usa para las llamadas |
| [Obsidian](https://obsidian.md) | Donde vives tus notas |
| Plugin **Spaced Repetition** de Obsidian | Para repasar las flashcards |

## 3. Instalación

### 3.1 study-agent

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.sh | sh
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.ps1 | iex
```

El instalador detecta tu sistema, descarga el binario de la última versión, verifica su
checksum SHA-256 y lo deja en tu PATH:

- macOS / Linux: `~/.local/bin/study-agent`. Si esa carpeta no está en tu PATH, el instalador te
  dice la línea exacta que debes añadir a `~/.zshrc` o `~/.bashrc`.
- Windows: `%LOCALAPPDATA%\Programs\study-agent\study-agent.exe` (se añade solo al PATH;
  abre una terminal nueva).

Comprueba la instalación:
```bash
study-agent --version
```

### 3.2 Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash     # macOS / Linux
irm https://claude.ai/install.ps1 | iex            # Windows
```

Inicia sesión una vez: ejecuta `claude`, elige **Claude account**, entra con tu cuenta Pro/Max y
sal con `/exit`.

### 3.3 Obsidian

1. Abre (o crea) tu vault.
2. *Settings → Community plugins → Browse* → instala y activa **Spaced Repetition**.
3. Los diagramas Mermaid y los callouts ya vienen incluidos en Obsidian.

## 4. Primeros pasos (5 minutos)

```bash
# 1. Configura la carpeta de tu vault (solo la primera vez)
study-agent init

# 2. Mira qué va a leer, sin gastar uso de Claude
study-agent list https://learn.microsoft.com/es-es/training/paths/ai-concepts/

# 3. Genera las notas del primer módulo de la ruta
study-agent generate https://learn.microsoft.com/es-es/training/paths/ai-concepts/ --only 1
```

Abre Obsidian y entra en `Certificaciones/AI-901/`. Empieza por la nota
**AI-901 - Mapa de estudio**.

> 💡 Para una primera prueba barata usa `--model haiku`.

## 5. Comandos

```
study-agent [-c RUTA] <comando> [opciones]
```

| Comando | Qué hace | ¿Usa Claude? |
| --- | --- | --- |
| `init` | Crea tu configuración y te pide la carpeta del vault | No |
| `exams` | Lista los temarios disponibles (`*` = el activo) | No |
| `list <url>` | Muestra los módulos y unidades que se leerán | No |
| `generate <url>` | Genera las notas en tu vault | **Sí** |

Opciones globales: `-c/--config RUTA` (usar otro archivo de configuración), `--version`, `--help`.
Cada comando tiene su ayuda: `study-agent generate --help`.

### `init`
```bash
study-agent init                          # pregunta la ruta del vault
study-agent init --vault ~/Obsidian/Mi    # sin preguntar
study-agent init --force                  # sobrescribe una configuración existente
```

### `list`
```bash
study-agent list <url>                    # ruta, módulo o unidad
study-agent list <url-de-ruta> --only 2 3
```
Útil para saber cuántos módulos tiene una ruta y elegir cuáles generar.

### `generate`
```bash
study-agent generate <url> [--only N ...] [--model M] [--exam ID] [--force]
```

| Opción | Descripción |
| --- | --- |
| `--only 1 3` | En una ruta, procesa solo esos módulos (numeración de `list`, empezando en 1) |
| `--model` | `sonnet` (por defecto, equilibrio), `opus` (máxima calidad, más cuota), `haiku` (rápido y barato) |
| `--exam` | Temario con el que clasificar (ver [sección 9](#9-otros-temarios-y-certificaciones)) |
| `--force` | Ignora la caché y vuelve a generar todo |

**Tipos de URL aceptados**

| Tipo | Ejemplo | Resultado |
| --- | --- | --- |
| Ruta | `.../training/paths/ai-concepts/` | Una nota por cada módulo de la ruta |
| Módulo | `.../training/modules/rag-fundamentals/` | Una nota con todas sus unidades |
| Unidad | `.../training/modules/get-started-ai-fundamentals/7-responsible-ai` | Una nota solo de esa unidad |

Puedes pegar URLs en inglés: se reescriben al idioma configurado (`es-es` por defecto).

**Códigos de salida**: `0` todo bien · `1` algún módulo falló o hubo un error · `2` uso incorrecto
(p. ej. `--only` fuera de rango) · `130` interrumpido con Ctrl+C.

## 6. Qué se genera en Obsidian

```
<vault>/Certificaciones/AI-901/
├── AI-901 - Mapa de estudio.md     ← empieza aquí
├── Módulos/
│   └── <título del módulo>.md
├── Conceptos/
│   └── <concepto>.md
└── .study-agent/index.json         (índice interno, no lo edites)
```

### Mapa de estudio
El temario oficial completo, por **dominio** (con su peso en el examen) y **habilidad**:
- ✅ / ⬜ indica qué habilidades ya tienen módulos estudiados.
- Enlaza a cada módulo y resume cuántos conceptos, preguntas y flashcards llevas.
- Se actualiza solo cada vez que generas un módulo.

### Nota de módulo
| Sección | Contenido |
| --- | --- |
| Cabecera | Dominio y habilidad del temario, por qué se clasificó ahí y enlace a Learn |
| Puntos clave | 5–8 ideas que debes recordar para el examen |
| Resumen | 250–450 palabras orientadas al examen, con enlaces a los conceptos |
| Conceptos clave | Definición de cada concepto; ⭐ los más importantes y ⚠️ las trampas típicas del examen |
| Mapa conceptual | Diagrama Mermaid; los nodos que son conceptos son clicables |
| Preguntas tipo examen | Opción única, selección múltiple, Sí/No y escenarios, con la respuesta plegada |
| Flashcards | Tarjetas `pregunta::respuesta` para Spaced Repetition |
| Unidades de Learn | Enlaces a las páginas originales |

En el frontmatter tienes `estado: por-repasar`. Cámbialo (p. ej. a `dominado`) para llevar tu
progreso: **se respeta aunque regeneres la nota**.

### Notas de concepto
Una nota por concepto (p. ej. `Retrieval Augmented Generation (RAG).md`) con su definición, la
trampa de examen, conceptos relacionados y la sección **Aparece en**, que enlaza todos los
módulos donde sale. Así el *graph view* de Obsidian muestra cómo se conecta el temario.

### Etiquetas
- `#ai-901`, `#ai-901/<dominio>`, `#ai-901/<habilidad>` en los módulos.
- `#ai-901/concepto` en los conceptos.
- Mazo de flashcards: `#flashcards/ai-901/<módulo>`.

## 7. Cómo estudiar con las notas

Un flujo que funciona bien:

1. **Mapa de estudio** → elige una habilidad ⬜ con mucho peso en el examen.
2. **Puntos clave y resumen** del módulo (5 minutos).
3. **Mapa conceptual**: intenta explicar en voz alta cada relación.
4. **Preguntas tipo examen**: responde *antes* de abrir la respuesta. Las que falles, anótalas.
5. **Flashcards**: abre la paleta de comandos → *Spaced Repetition: Review flashcards* y repasa a
   diario; el plugin programa los repasos según lo bien que respondas.
6. Cambia `estado:` de la nota cuando la domines.

> Los conceptos con ⚠️ **Trampa de examen** son los distractores más probables: repásalos justo
> antes del examen.

## 8. Configuración

`study-agent init` crea el archivo. Solo necesitas las claves que quieras cambiar; el resto toma
los valores por defecto.

| Sistema | Archivo de configuración | Caché |
| --- | --- | --- |
| macOS / Linux | `~/.config/study-agent/config.yaml` | `~/.cache/study-agent/` |
| Windows | `%APPDATA%\study-agent\config.yaml` | `%LOCALAPPDATA%\study-agent\cache\` |

```yaml
vault_path: "/Users/ana/Obsidian/Estudio"   # obligatorio: carpeta del vault
# base_folder: "Certificaciones/AI-901"     # por defecto Certificaciones/<CÓDIGO del temario>
exam: "ai-901"                              # temario activo
learn_locale: "es-es"                       # idioma de Learn (en-us, pt-br...)

claude:
  bin: "claude"            # ruta del ejecutable de Claude Code
  model: "sonnet"          # sonnet | opus | haiku
  timeout_seconds: 900     # tiempo máximo por llamada
  use_json_schema: true    # salida estructurada (desactívalo solo con Claude Code antiguo)

generation:
  questions_per_module: 10
  flashcards_per_module: 20
  skip_units_matching: ["exercise", "knowledge-check"]   # omite laboratorios y evaluaciones
```

**Variables de entorno**

| Variable | Efecto |
| --- | --- |
| `STUDY_AGENT_VAULT` | Sustituye a `vault_path` |
| `STUDY_AGENT_CONFIG` | Ruta del archivo de configuración |
| `STUDY_AGENT_CONFIG_DIR` | Carpeta de configuración (y de temarios propios) |
| `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` | Bases estándar de configuración y caché |

## 9. Otros temarios y certificaciones

`study-agent exams` lista los temarios disponibles. Hoy incluye **AI-901 (Azure AI Fundamentals)**,
pero puedes añadir cualquier otro creando un YAML en la carpeta `exams/` de tu configuración
(`~/.config/study-agent/exams/` o `%APPDATA%\study-agent\exams\`):

```yaml
# ~/.config/study-agent/exams/az-900.yaml
code: AZ-900
name: "Microsoft Azure Fundamentals"
passing_score: 700
domains:
  - id: conceptos-cloud
    name: "Describir conceptos de la nube"
    weight: "25–30%"
    skills:
      - id: computacion-nube
        name: "Computación en la nube"
        details: "Modelo de responsabilidad compartida, nube pública, privada e híbrida..."
  # ... resto de dominios del study guide oficial
```

- Copia los dominios y habilidades del *study guide* oficial de la certificación.
- Los `id` deben ser cortos, sin espacios y únicos: se usan en las etiquetas.
- Úsalo con `--exam az-900` o pon `exam: "az-900"` en tu configuración.
- Las notas irán a `Certificaciones/AZ-900/`.
- Un archivo con el mismo nombre que uno incluido (p. ej. `ai-901.yaml`) lo sustituye.

## 10. Consumo de tu suscripción y caché

- Cada módulo hace **3 llamadas** a Claude. Una ruta de 7 módulos son 21 llamadas.
- Consume tu límite de uso como cualquier sesión de Claude Code. `haiku` gasta menos; `opus`, más.
- `list` nunca llama a Claude: úsalo para planificar.
- **Caché por etapa**: cada etapa terminada se guarda. Si te quedas sin cuota a mitad de una ruta,
  vuelve a ejecutar el mismo comando más tarde y continuará donde se quedó (verás `↺ … (caché)`).
- La caché se invalida sola si cambia el contenido en Learn, el modelo o el número de preguntas
  o flashcards. Para forzar la regeneración: `--force`.

## 11. Uso con Docker

Alternativa si no quieres instalar nada salvo Docker:

```bash
git clone https://github.com/byrogr/azure-study-agent && cd azure-study-agent
docker build -t azure-study-agent .
docker run --rm -it --entrypoint claude azure-study-agent setup-token   # copia el token
cp .env.example .env     # pon VAULT_DIR (tu vault) y CLAUDE_CODE_OAUTH_TOKEN
docker compose run --rm study-agent generate <url> --only 1
```

El vault se monta en `/vault` y la caché vive en un volumen de Docker. `.env` contiene tu token:
no lo compartas ni lo subas a git.

## 12. Actualizar y desinstalar

**Actualizar**: vuelve a ejecutar el instalador. Para una versión concreta:
```bash
curl -fsSL https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.sh | STUDY_AGENT_VERSION=v0.1.0 sh
```
```powershell
$env:STUDY_AGENT_VERSION = 'v0.1.0'; irm https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.ps1 | iex
```

**Desinstalar**
- macOS / Linux: `rm ~/.local/bin/study-agent` y, si quieres borrar también configuración y caché,
  `rm -rf ~/.config/study-agent ~/.cache/study-agent`.
- Windows: borra `%LOCALAPPDATA%\Programs\study-agent`, `%APPDATA%\study-agent` y
  `%LOCALAPPDATA%\study-agent`, y quita la primera carpeta de tu PATH de usuario.

Tus notas de Obsidian **no se borran**: son tuyas.

## 13. Solución de problemas

| Mensaje / síntoma | Causa y solución |
| --- | --- |
| `study-agent: command not found` | La carpeta de instalación no está en el PATH. Añade la línea que mostró el instalador o abre una terminal nueva (Windows). |
| `No hay vault configurado. Ejecuta study-agent init` | Aún no has configurado el vault: ejecuta `study-agent init`. |
| `Claude Code no tiene sesión iniciada…` | Ejecuta `claude` e inicia sesión. En Docker, revisa `CLAUDE_CODE_OAUTH_TOKEN` en `.env`. |
| `No encuentro el CLI claude` | Instala Claude Code ([3.2](#32-claude-code)) o indica su ruta en `claude.bin`. |
| Error de límite de uso / *rate limit* | Has llegado al límite de tu plan. Espera y vuelve a ejecutar: lo hecho queda en caché. |
| `superó el timeout` | Módulo muy largo o red lenta. Sube `claude.timeout_seconds` o usa `--model haiku`. |
| `URL no reconocida como ruta, módulo o unidad de Learn` | La URL no es de `learn.microsoft.com/.../training/...`. Copia la URL desde el navegador. |
| `--only fuera de rango` | La ruta tiene menos módulos. Mira la numeración con `study-agent list <url>`. |
| `error de red con Microsoft Learn` | Problema de conexión o Learn caído. Reintenta. |
| macOS: *“no se puede abrir porque es de un desarrollador no identificado”* | Pasa si descargaste el binario con el navegador. Usa el instalador de una línea o ejecuta `xattr -d com.apple.quarantine ~/.local/bin/study-agent`. |
| Windows: SmartScreen bloquea el `.exe` | El binario no está firmado. Usa el instalador de PowerShell o pulsa *Más información → Ejecutar de todas formas*. |
| Las notas salen en otra carpeta | Revisa `vault_path` y `base_folder` en tu configuración. |

## 14. Preguntas frecuentes

**¿Necesito una API key de Anthropic?**
No. Usa tu sesión de Claude Code, es decir, tu suscripción Pro/Max.

**¿Puedo usarlo para otras fuentes además de Microsoft Learn?**
Todavía no: hoy solo lee Microsoft Learn. Sí puedes usar cualquier temario (sección 9).

**¿Qué pasa si regenero un módulo?**
La nota del módulo se reescribe (se conserva tu `estado:`). Las notas de concepto existentes no se
modifican; solo se les añade el enlace al nuevo módulo. Si editas el cuerpo de una nota de módulo,
esos cambios se pierden cada vez que vuelves a ejecutar `generate` sobre ese módulo: escribe tus
apuntes propios en notas aparte y enlázalas.

**¿En qué idioma salen las notas?**
En español. Los nombres de productos y términos que Microsoft usa en el examen se mantienen en
inglés.

**¿Mis notas o datos se envían a algún sitio?**
Solo el contenido de Learn que se procesa se envía a Claude a través de Claude Code. Las notas se
escriben en tu disco.

**¿Dónde reporto un problema o sugiero algo?**
En [GitHub Issues](https://github.com/byrogr/azure-study-agent/issues).
