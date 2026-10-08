"""Orquestación del flujo por módulo, con caché por etapa.

Si una ejecución se corta (límite de uso de la suscripción, red...), al volver a
lanzarla se reutilizan las etapas ya hechas mientras el contenido no haya cambiado.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import prompts
from .llm import ClaudeCLI


class Pipeline:
    def __init__(self, llm: ClaudeCLI, exam: dict, cache_dir: Path, gen_cfg: dict, log=print):
        self.llm = llm
        self.exam = exam
        self.cache_dir = cache_dir
        self.n_questions = int(gen_cfg.get("questions_per_module", 10))
        self.n_cards = int(gen_cfg.get("flashcards_per_module", 20))
        self.log = log

    def _cached(self, key: str, stage: str, fn):
        path = self.cache_dir / key / f"{stage}.json"
        if path.exists():
            self.log(f"   ↺ {stage} (caché)")
            return json.loads(path.read_text(encoding="utf-8"))
        self.log(f"   → {stage}…")
        result = fn()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def run(self, module, force: bool = False) -> tuple[dict, dict, dict]:
        content = module.content
        params = f"{self.exam['code']}|{self.llm.model}|{self.n_questions}|{self.n_cards}|{prompts.PROMPT_VERSION}"
        digest = hashlib.sha256((content + params).encode()).hexdigest()[:12]
        key = f"{module.slug}-{digest}"
        if force:
            for f in (self.cache_dir / key).glob("*.json"):
                f.unlink()
        title = module.title or module.slug

        # 1) clasificar tema + extraer conceptos
        analysis = self._cached(key, "1-clasificar-y-conceptos", lambda: self.llm.ask_json(
            prompts.SYSTEM, prompts.analyze_prompt(self.exam, title, content), prompts.ANALYZE_SCHEMA))
        concepts = analysis["conceptos"]

        # 2) resumen + mapa conceptual
        study = self._cached(key, "2-resumen-y-mapa", lambda: self.llm.ask_json(
            prompts.SYSTEM, prompts.study_prompt(title, content, concepts), prompts.STUDY_SCHEMA))

        # 3) preguntas tipo examen + flashcards
        practice = self._cached(key, "3-preguntas-y-flashcards", lambda: self._practice(title, content, concepts))
        return analysis, study, practice

    def _practice(self, title: str, content: str, concepts: list[dict]) -> dict:
        schema = copy.deepcopy(prompts.PRACTICE_SCHEMA)
        schema["properties"]["preguntas"]["minItems"] = self.n_questions
        schema["properties"]["flashcards"]["minItems"] = self.n_cards
        prompt = prompts.practice_prompt(self.exam, title, content, concepts, self.n_questions, self.n_cards)
        best = None
        for _ in range(2):
            out = self.llm.ask_json(prompts.SYSTEM, prompt, schema)
            if best is None or len(out["preguntas"]) + len(out["flashcards"]) > \
                    len(best["preguntas"]) + len(best["flashcards"]):
                best = out
            if len(out["preguntas"]) >= self.n_questions * 0.8 and len(out["flashcards"]) >= self.n_cards * 0.8:
                return out
            self.log(f"   ⚠ solo {len(out['preguntas'])} preguntas / {len(out['flashcards'])} flashcards; reintentando")
            prompt += (f"\n\nOBLIGATORIO: entrega EXACTAMENTE {self.n_questions} preguntas y "
                       f"{self.n_cards} flashcards. Tu intento anterior se quedó corto.")
        return best
