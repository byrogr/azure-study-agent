"""Tests unitarios offline (sin red ni Claude).

Uso: python -m unittest discover tests
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FX = ROOT / "tests" / "fixtures"

from study_agent import cli, learn, llm, obsidian, paths  # noqa: E402


class LearnTests(unittest.TestCase):
    def setUp(self):
        self.client = learn.LearnClient("es-es")

    def test_normalize_and_kind(self):
        url = self.client.normalize("https://learn.microsoft.com/en-us/training/modules/foo/2-bar?x=1#y")
        self.assertEqual(url, "https://learn.microsoft.com/es-es/training/modules/foo/2-bar")
        self.assertEqual(self.client.kind(url), "unit")
        self.assertEqual(self.client.kind(url.rsplit("/", 1)[0] + "/"), "module")
        self.assertEqual(self.client.kind("https://learn.microsoft.com/es-es/training/paths/p/"), "path")
        with self.assertRaises(ValueError):
            self.client.kind("https://learn.microsoft.com/es-es/docs/")

    def test_noise_removes_anton_promo_but_keeps_content(self):
        md, title = learn.clean_unit_markdown((FX / "1-introduction.md").read_text(encoding="utf-8"))
        self.assertNotIn("choose-anton", md)
        self.assertNotIn("Pregunte a Anton", md)
        text, _ = learn.clean_unit_markdown("# T\n\nAntonio usa el cantón de Zug.\n")
        self.assertIn("Antonio usa el cantón de Zug.", text)

    def test_list_modules_from_fixture(self):
        with mock.patch.object(learn.LearnClient, "_get", lambda s, u, markdown=False: (FX / "path.html").read_text(encoding="utf-8")):
            title, mods = self.client.list_modules("https://learn.microsoft.com/es-es/training/paths/ai-concepts/")
        self.assertTrue(mods)
        self.assertTrue(all("/es-es/training/modules/" in m for m in mods))
        self.assertEqual(len(mods), len(set(mods)))

    def test_relative_links_as_served_by_learn(self):
        path_html = ('<h2>Requisitos previos</h2><a href="../../modules/prereq/">x</a>'
                     '<h2 class="t">Módulos en esta ruta de aprendizaje</h2>'
                     '<a href="../../modules/mod-a/">A</a><a href="../../modules/mod-a/">A</a>'
                     '<a href="../../modules/mod-b/">B</a>')
        module_html = ('<a class="unit-title" href="1-introduction" data-linktype="relative-path">Intro</a>'
                       '<a class="unit-title" href="2-exercise">Lab</a>')
        with mock.patch.object(learn.LearnClient, "_get", lambda s, u, markdown=False:
                               path_html if "/paths/" in u else module_html):
            _, mods = self.client.list_modules("https://learn.microsoft.com/es-es/training/paths/p/")
            mod = self.client.load_module(mods[0], skip=["exercise"], fetch_units=False)
        self.assertEqual([m.rstrip("/").split("/")[-1] for m in mods], ["mod-a", "mod-b"])
        self.assertEqual([(u.slug, u.title) for u in mod.units], [("1-introduction", "Intro")])
        self.assertEqual(mod.units[0].url, "https://learn.microsoft.com/es-es/training/modules/mod-a/1-introduction")


class MermaidTests(unittest.TestCase):
    def test_ids_do_not_collide(self):
        out = obsidian.render_mermaid({"central": "X", "nodos": [
            {"id": "a-b", "etiqueta": "A"}, {"id": "a_b", "etiqueta": "B"}],
            "relaciones": [{"desde": "a-b", "hasta": "a_b", "etiqueta": "usa"}]}, set())
        self.assertIn('n_a_b["A"]', out)
        self.assertIn('n_a_b_2["B"]', out)
        self.assertIn('n_a_b -->|"usa"| n_a_b_2', out)

    def test_concept_nodes_link_even_with_unsafe_chars(self):
        out = obsidian.render_mermaid({"central": "X", "nodos": [{"id": "v", "etiqueta": "Azure AI: Vision"}],
                                       "relaciones": []}, {"Azure AI: Vision"})
        self.assertIn("class n_v internal-link", out)


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        exam = paths.load_exam("ai-901")
        self.vault = obsidian.Vault(self.tmp.name, "Cert", exam)
        self.analysis = {"dominio_id": "conceptos", "habilidad_id": "modelos", "justificacion": "j",
                         "relevancia_examen": "alta", "conceptos": [
                             {"nombre": "Token", "definicion": "d", "importancia": "alta", "relacionados": []}]}
        self.study = {"resumen": "r", "puntos_clave": ["p"], "mapa": {"central": "c", "nodos": [], "relaciones": []}}
        opts = [f"o{i}" for i in range(9)]
        self.practice = {"preguntas": [{"tipo": "opcion_unica", "enunciado": "e", "opciones": opts,
                                        "correctas": [8], "explicacion": "x", "concepto": "Token"}],
                         "flashcards": [{"frente": "a", "reverso": "b"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def module(self, slug, title="Mismo título"):
        return SimpleNamespace(url=f"https://learn.microsoft.com/es-es/training/modules/{slug}/",
                               slug=slug, title=title, uid="", path_title="", units=[])

    def test_many_options_and_state_preserved(self):
        path = self.vault.write_module(self.module("m1"), self.analysis, self.study, self.practice)
        self.assertIn("**I**", path.read_text(encoding="utf-8"))
        path.write_text(path.read_text(encoding="utf-8").replace("estado: por-repasar", "estado: dominado"),
                        encoding="utf-8")
        path2 = self.vault.write_module(self.module("m1"), self.analysis, self.study, self.practice)
        self.assertEqual(path, path2)
        self.assertIn("estado: dominado", path2.read_text(encoding="utf-8"))

    def test_same_title_does_not_overwrite(self):
        p1 = self.vault.write_module(self.module("m1"), self.analysis, self.study, self.practice)
        p2 = self.vault.write_module(self.module("m2"), self.analysis, self.study, self.practice)
        self.assertNotEqual(p1, p2)
        self.assertTrue(p1.exists() and p2.exists())


class LLMTests(unittest.TestCase):
    def proc(self, code=0, stdout="", stderr=""):
        return subprocess.CompletedProcess([], code, stdout, stderr)

    def test_extract_json_from_fence(self):
        self.assertEqual(llm.extract_json('texto\n```json\n{"a": 1}\n```'), {"a": 1})

    def test_usage_limit_is_not_retried(self):
        cli = llm.ClaudeCLI(use_json_schema=False)
        with mock.patch("subprocess.run", return_value=self.proc(1, stderr="Claude usage limit reached")) as run:
            with self.assertRaises(llm.LLMError):
                cli.ask_json("s", "p")
        self.assertEqual(run.call_count, 1)

    def test_not_logged_in_is_not_retried_and_explains(self):
        out = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})
        cli_ = llm.ClaudeCLI(use_json_schema=False)
        with mock.patch("subprocess.run", return_value=self.proc(1, stdout=out)) as run:
            with self.assertRaises(llm.LLMError) as ctx:
                cli_.ask_json("s", "p")
        self.assertEqual(run.call_count, 1)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", str(ctx.exception))

    def test_invalid_json_is_retried_with_nudge(self):
        bad = self.proc(stdout=json.dumps({"result": "no json"}))
        good = self.proc(stdout=json.dumps({"result": '{"ok": true}'}))
        cli = llm.ClaudeCLI(use_json_schema=False)
        with mock.patch("subprocess.run", side_effect=[bad, good]) as run:
            self.assertEqual(cli.ask_json("s", "p"), {"ok": True})
        self.assertIn("IMPORTANTE", run.call_args_list[1].kwargs["input"])


class PathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        env = {"STUDY_AGENT_CONFIG_DIR": str(self.dir / "cfg"), "XDG_CACHE_HOME": str(self.dir / "cache")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        for k in ("STUDY_AGENT_CONFIG", "STUDY_AGENT_VAULT"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_defaults_without_user_config(self):
        cfg = paths.load_config()
        self.assertEqual(cfg["exam"], "ai-901")
        self.assertNotIn("base_folder", cfg)  # se deriva del temario: no fijarlo a AI-901
        self.assertEqual(paths.cache_dir(), self.dir / "cache" / "study-agent")
        with self.assertRaises(paths.ConfigError):  # placeholder TU_USUARIO
            paths.require_vault(cfg)

    def test_user_config_merges_and_env_vault_wins(self):
        (self.dir / "cfg").mkdir()
        (self.dir / "cfg" / "config.yaml").write_text("vault_path: /a\nclaude: {model: opus}\n")
        cfg = paths.load_config()
        self.assertEqual(cfg["claude"]["model"], "opus")
        self.assertEqual(cfg["claude"]["bin"], "claude")  # default conservado
        self.assertEqual(paths.require_vault(cfg), "/a")
        with mock.patch.dict(os.environ, {"STUDY_AGENT_VAULT": "/b"}):
            self.assertEqual(paths.load_config()["vault_path"], "/b")
        with self.assertRaises(paths.ConfigError):
            paths.load_config(str(self.dir / "no-existe.yaml"))

    def test_user_exam_overrides_packaged(self):
        (self.dir / "cfg" / "exams").mkdir(parents=True)
        (self.dir / "cfg" / "exams" / "ai-901.yaml").write_text("code: MINE\nname: x\ndomains: []\n")
        (self.dir / "cfg" / "exams" / "cka.yaml").write_text("code: CKA\nname: k\ndomains: []\n")
        self.assertEqual(paths.load_exam("ai-901")["code"], "MINE")
        self.assertIn("cka", paths.list_exams())
        with self.assertRaises(paths.ConfigError):
            paths.load_exam("nope")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_init_then_generate_requires_no_flags(self):
        vault = self.dir / "vault"
        vault.mkdir()
        with mock.patch.object(llm.ClaudeCLI, "check"):
            code, out, _ = self.run_cli("init", "--vault", str(vault))
        self.assertEqual(code, 0)
        self.assertEqual(paths.require_vault(paths.load_config()), str(vault.resolve()))
        code, _, err = self.run_cli("init", "--vault", str(vault))
        self.assertEqual(code, 2)
        self.assertIn("--force", err)

    def test_init_escapes_windows_paths(self):
        vault = self.dir / "vault"
        vault.mkdir()
        fake = Path("C:\\Users\\ana\\Obsidian")
        with mock.patch.object(llm.ClaudeCLI, "check"), \
                mock.patch.object(cli.Path, "resolve", return_value=fake), \
                mock.patch.object(cli.Path, "is_dir", return_value=True):
            self.assertEqual(self.run_cli("init", "--vault", str(vault))[0], 0)
        self.assertEqual(paths.load_config()["vault_path"], str(fake))

    def test_list_subcommand_and_global_config_flag(self):
        cfg = self.dir / "c.yaml"
        cfg.write_text("learn_locale: es-es\n")
        fake = lambda s, u, markdown=False: (FX / ("path.html" if "/paths/" in u else "module.html")).read_text(encoding="utf-8")
        with mock.patch.object(learn.LearnClient, "_get", fake):
            code, out, _ = self.run_cli("-c", str(cfg), "list",
                                        "https://learn.microsoft.com/en-us/training/paths/ai-concepts/", "--only", "1")
        self.assertEqual(code, 0)
        self.assertIn("1-introduction", out)
        self.assertNotIn("7b-exercise", out)
        code, _, err = self.run_cli("list", "https://example.com/x")
        self.assertEqual(code, 1)
        self.assertIn("URL no reconocida", err)
        self.assertIn("https://example.com/x", err)


if __name__ == "__main__":
    unittest.main()
