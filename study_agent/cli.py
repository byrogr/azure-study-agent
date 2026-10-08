"""CLI: python -m study_agent <URL de Microsoft Learn> [opciones]

Acepta URL de ruta de aprendizaje, de módulo o de unidad.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import yaml

from .learn import LearnClient
from .llm import ClaudeCLI, LLMError
from .obsidian import Vault
from .pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"No encuentro {path}. Copia config.example.yaml como config.yaml y ajusta vault_path.")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="study-agent",
                                 description="Convierte contenido de Microsoft Learn en notas de estudio para Obsidian.")
    ap.add_argument("url", help="URL de una ruta, módulo o unidad de Microsoft Learn")
    ap.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--exam", help="Examen (archivo en exams/), p. ej. ai-901")
    ap.add_argument("--model", help="Modelo de Claude: sonnet, opus, haiku")
    ap.add_argument("--only", type=int, nargs="+", metavar="N",
                    help="En una ruta, procesa solo los módulos N (1-based), p. ej. --only 1 3")
    ap.add_argument("--list", action="store_true", help="Solo lista módulos/unidades, sin llamar a Claude")
    ap.add_argument("--force", action="store_true", help="Ignora la caché y regenera")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config))
    if os.environ.get("STUDY_AGENT_VAULT"):  # p. ej. en Docker, donde el vault se monta en /vault
        cfg["vault_path"] = os.environ["STUDY_AGENT_VAULT"]
    exam_id = args.exam or cfg.get("exam", "ai-901")
    exam = yaml.safe_load((ROOT / "exams" / f"{exam_id}.yaml").read_text(encoding="utf-8"))
    gen = cfg.get("generation", {})
    learn = LearnClient(cfg.get("learn_locale", "es-es"))
    skip = gen.get("skip_units_matching", ["exercise", "knowledge-check"])

    url = learn.normalize(args.url)
    kind = learn.kind(url)
    path_title = ""
    if kind == "path":
        path_title, module_urls = learn.list_modules(url)
        print(f"📚 Ruta: {path_title} — {len(module_urls)} módulos")
        for i, m in enumerate(module_urls, 1):
            print(f"   {i}. {m}")
        if args.only:
            bad = [i for i in args.only if not 0 < i <= len(module_urls)]
            if bad:
                sys.exit(f"--only fuera de rango (la ruta tiene {len(module_urls)} módulos): {bad}")
            module_urls = [module_urls[i - 1] for i in args.only]
    else:
        module_urls = [url]

    if args.list:
        if kind == "unit":
            mod = learn.load_single_unit(url)
            print(f"\n📄 {mod.title} ({len(mod.content):,} caracteres)")
            return 0
        for m in module_urls:
            mod = learn.load_module(m, skip, path_title, fetch_units=False)
            print(f"\n📦 {mod.title} ({len(mod.units)} unidades)")
            for u in mod.units:
                print(f"   - {u.slug}: {u.title}")
        return 0

    c = cfg.get("claude", {})
    llm = ClaudeCLI(c.get("bin", "claude"), args.model or c.get("model", "sonnet"),
                    int(c.get("timeout_seconds", 900)), bool(c.get("use_json_schema", True)))
    llm.check()
    vault = Vault(cfg["vault_path"], cfg.get("base_folder", f"Certificaciones/{exam['code']}"), exam)
    pipe = Pipeline(llm, exam, ROOT / ".cache", gen)

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
            print(f"   ❌ Claude: {e}\n   Vuelve a ejecutar más tarde; las etapas hechas quedan en caché.")
        except Exception as e:  # noqa: BLE001 — seguimos con el resto de módulos
            failures += 1
            print(f"   ❌ {type(e).__name__}: {e}")

    print(f"\nListo. Mapa de estudio: {vault.write_moc().relative_to(vault.root)} · "
          f"{llm.calls} llamadas a Claude")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
