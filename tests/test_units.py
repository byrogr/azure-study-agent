"""Tests unitarios offline (sin red ni Claude).

Uso: python -m unittest discover tests
"""
import json
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

import yaml  # noqa: E402

from study_agent import learn, llm, obsidian  # noqa: E402


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
        exam = yaml.safe_load((ROOT / "exams" / "ai-901.yaml").read_text(encoding="utf-8"))
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

    def test_invalid_json_is_retried_with_nudge(self):
        bad = self.proc(stdout=json.dumps({"result": "no json"}))
        good = self.proc(stdout=json.dumps({"result": '{"ok": true}'}))
        cli = llm.ClaudeCLI(use_json_schema=False)
        with mock.patch("subprocess.run", side_effect=[bad, good]) as run:
            self.assertEqual(cli.ask_json("s", "p"), {"ok": True})
        self.assertIn("IMPORTANTE", run.call_args_list[1].kwargs["input"])


if __name__ == "__main__":
    unittest.main()
