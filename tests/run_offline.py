"""Prueba end-to-end sin red hacia Microsoft Learn: sirve fixtures locales y usa Claude real.

Uso: python tests/run_offline.py <vault_dir> [modelo]
"""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FX = ROOT / "tests" / "fixtures"

from study_agent import cli, learn  # noqa: E402


def fake_get(self, url, markdown=False):
    slug = url.rstrip("/").split("/")[-1]
    if "/training/paths/" in url:
        return (FX / "path.html").read_text(encoding="utf-8")
    if markdown:
        return (FX / f"{slug}.md").read_text(encoding="utf-8")
    return (FX / "module.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    vault = Path(sys.argv[1])
    vault.mkdir(parents=True, exist_ok=True)
    model = sys.argv[2] if len(sys.argv) > 2 else "haiku"
    cfg = vault.parent / "config.test.yaml"
    cfg.write_text(f"vault_path: {vault}\nbase_folder: Certificaciones/AI-901\nexam: ai-901\n"
                   f"claude: {{model: {model}}}\n"
                   "generation: {questions_per_module: 6, flashcards_per_module: 10, skip_units_matching: [exercise]}\n")
    with mock.patch.object(learn.LearnClient, "_get", fake_get):
        sys.exit(cli.main(["generate", "https://learn.microsoft.com/en-us/training/paths/ai-concepts/",
                           "-c", str(cfg), "--only", "1"] + sys.argv[3:]))
