"""CLI: study-agent <comando> [opciones]

  study-agent init                     crea la configuración (vault de Obsidian)
  study-agent exams                    temarios disponibles
  study-agent list <url>               qué módulos/unidades se leerán (sin Claude)
  study-agent generate <url>           genera las notas de estudio
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from . import __version__, paths
from .learn import LearnClient
from .llm import ClaudeCLI, LLMError
from .obsidian import Vault
from .pipeline import Pipeline

DEFAULT_SKIP = ["exercise", "knowledge-check"]


class UsageError(RuntimeError):
    pass


# ---------------------------------------------------------------- fuentes
def discover(learn: LearnClient, target: str, only: list[int] | None) -> tuple[str, str, list[str]]:
    """Resuelve el destino en (tipo, título de la ruta, URLs a procesar).

    Hoy solo Microsoft Learn; aquí se enchufarán otras fuentes (archivos, PDF, web).
    """
    url = learn.normalize(target)
    kind = learn.kind(url)
    if kind != "path":
        if only:
            raise UsageError("--only solo aplica a URLs de rutas de aprendizaje")
        return kind, "", [url]
    path_title, module_urls = learn.list_modules(url)
    print(f"📚 Ruta: {path_title} — {len(module_urls)} módulos")
    for i, m in enumerate(module_urls, 1):
        print(f"   {i}. {m}")
    if only:
        bad = [i for i in only if not 0 < i <= len(module_urls)]
        if bad:
            raise UsageError(f"--only fuera de rango (la ruta tiene {len(module_urls)} módulos): {bad}")
        module_urls = [module_urls[i - 1] for i in only]
    return kind, path_title, module_urls


def _learn(cfg: dict) -> tuple[LearnClient, list[str]]:
    gen = cfg.get("generation", {})
    return LearnClient(cfg.get("learn_locale", "es-es")), gen.get("skip_units_matching", DEFAULT_SKIP)


# ---------------------------------------------------------------- comandos
def cmd_init(args) -> int:
    target = paths.user_config_path(args.config)
    if target.exists() and not args.force:
        raise UsageError(f"Ya existe {target}. Usa --force para sobrescribirla.")
    vault = args.vault or input("Ruta de tu vault de Obsidian: ").strip()
    vault_path = Path(vault).expanduser().resolve()
    if not vault_path.is_dir():
        raise UsageError(f"No existe la carpeta del vault: {vault_path}")
    template = paths.config_template()
    placeholder = next(ln for ln in template.splitlines() if ln.startswith("vault_path:"))
    target.parent.mkdir(parents=True, exist_ok=True)
    # json.dumps escapa las barras invertidas de Windows (C:\\Users\\...) para YAML
    target.write_text(template.replace(placeholder, f"vault_path: {json.dumps(str(vault_path))}"), encoding="utf-8")
    print(f"✅ Configuración creada en {target}")
    try:
        ClaudeCLI().check()
    except LLMError as e:
        print(f"⚠️  {e}", file=sys.stderr)
    return 0


def cmd_exams(args) -> int:
    cfg = paths.load_config(args.config)
    for exam_id, exam in paths.list_exams().items():
        mark = "*" if exam_id == cfg.get("exam") else " "
        print(f"{mark} {exam_id:<12} {exam.get('code', '')} · {exam.get('name', '')}")
    print(f"\nTemarios propios: {paths.config_dir() / 'exams' / '<id>.yaml'}")
    return 0


def cmd_list(args) -> int:
    learn, skip = _learn(paths.load_config(args.config))
    kind, path_title, module_urls = discover(learn, args.url, args.only)
    if kind == "unit":
        mod = learn.load_single_unit(module_urls[0])
        print(f"\n📄 {mod.title} ({len(mod.content):,} caracteres)")
        return 0
    for m in module_urls:
        mod = learn.load_module(m, skip, path_title, fetch_units=False)
        print(f"\n📦 {mod.title} ({len(mod.units)} unidades)")
        for u in mod.units:
            print(f"   - {u.slug}: {u.title}")
    return 0


def cmd_generate(args) -> int:
    cfg = paths.load_config(args.config)
    vault_path = paths.require_vault(cfg)
    exam = paths.load_exam(args.exam or cfg.get("exam", "ai-901"))
    learn, skip = _learn(cfg)
    kind, path_title, module_urls = discover(learn, args.url, args.only)

    c = cfg.get("claude", {})
    llm = ClaudeCLI(c.get("bin", "claude"), args.model or c.get("model", "sonnet"),
                    int(c.get("timeout_seconds", 900)), bool(c.get("use_json_schema", True)))
    llm.check()
    vault = Vault(vault_path, cfg.get("base_folder", f"Certificaciones/{exam['code']}"), exam)
    pipe = Pipeline(llm, exam, paths.cache_dir(), cfg.get("generation", {}))

    failures = 0
    for i, m in enumerate(module_urls, 1):
        t0 = time.time()
        try:
            mod = learn.load_single_unit(m) if kind == "unit" else learn.load_module(m, skip, path_title)
            print(f"\n[{i}/{len(module_urls)}] 📦 {mod.title} — {len(mod.units)} unidades leídas")
            analysis, study, practice = pipe.run(mod, force=args.force)
            note = vault.write_module(mod, analysis, study, practice)
            print(f"   ✅ {note.relative_to(vault.root)} "
                  f"({len(analysis['conceptos'])} conceptos, {len(practice['preguntas'])} preguntas, "
                  f"{len(practice['flashcards'])} flashcards) en {time.time() - t0:.0f}s")
        except LLMError as e:
            failures += 1
            print(f"   ❌ Claude: {e}\n   Vuelve a ejecutar más tarde; las etapas hechas quedan en caché.",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — seguimos con el resto de módulos
            failures += 1
            print(f"   ❌ {type(e).__name__}: {e}", file=sys.stderr)

    print(f"\nListo. Mapa de estudio: {vault.write_moc().relative_to(vault.root)} · "
          f"{llm.calls} llamadas a Claude")
    return 1 if failures else 0


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    def config_opt(parser, default):
        parser.add_argument("-c", "--config", metavar="RUTA", default=default,
                            help=f"archivo de configuración (por defecto {paths.config_dir() / 'config.yaml'})")

    # En los subcomandos, SUPPRESS evita que su None pise un -c dado antes del comando
    common = argparse.ArgumentParser(add_help=False)
    config_opt(common, argparse.SUPPRESS)

    ap = argparse.ArgumentParser(
        prog="study-agent",
        description="Convierte contenido de Microsoft Learn en notas de estudio para Obsidian.")
    config_opt(ap, None)
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="<comando>")
    sub.required = True

    p = sub.add_parser("init", parents=[common], help="crea la configuración inicial")
    p.add_argument("--vault", metavar="RUTA", help="carpeta de tu vault de Obsidian")
    p.add_argument("--force", action="store_true", help="sobrescribe la configuración existente")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("exams", parents=[common], help="lista los temarios disponibles")
    p.set_defaults(func=cmd_exams)

    url_help = "URL de una ruta, módulo o unidad de Microsoft Learn"
    only_help = "en una ruta, solo los módulos N (1-based), p. ej. --only 1 3"

    p = sub.add_parser("list", parents=[common], help="muestra módulos y unidades sin llamar a Claude")
    p.add_argument("url", help=url_help)
    p.add_argument("--only", type=int, nargs="+", metavar="N", help=only_help)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("generate", parents=[common], help="genera las notas de estudio en el vault")
    p.add_argument("url", help=url_help)
    p.add_argument("--only", type=int, nargs="+", metavar="N", help=only_help)
    p.add_argument("--exam", metavar="ID", help="temario (ver `study-agent exams`), p. ej. ai-901")
    p.add_argument("--model", help="modelo de Claude: sonnet, opus, haiku")
    p.add_argument("--force", action="store_true", help="ignora la caché y regenera")
    p.set_defaults(func=cmd_generate)
    return ap


def _utf8_console() -> None:
    """La consola de Windows usa cp1252 por defecto: sin esto, los emojis rompen los print."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv=None) -> int:
    _utf8_console()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130
    except requests.RequestException as e:
        print(f"error de red con Microsoft Learn: {e}", file=sys.stderr)
        return 1
    except (UsageError, paths.ConfigError, LLMError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2 if isinstance(e, UsageError) else 1


if __name__ == "__main__":
    raise SystemExit(main())
