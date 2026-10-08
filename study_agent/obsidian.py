"""Escritura de notas en el vault de Obsidian.

Estructura generada dentro de <vault>/<base_folder>/:
  <EXAM> - Mapa de estudio.md   índice por dominio/habilidad con progreso
  Módulos/<título>.md           resumen, conceptos, mapa Mermaid, preguntas, flashcards
  Conceptos/<concepto>.md       una nota por concepto (enlazadas desde los módulos)
  .study-agent/index.json       índice interno para regenerar el mapa de estudio
"""
from __future__ import annotations

import json
import re
import string
from datetime import date
from pathlib import Path

INVALID = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe_name(name: str) -> str:
    return re.sub(r"\s+", " ", INVALID.sub("-", name)).strip(" .-")[:120]


def slugify(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


class Vault:
    def __init__(self, vault_path: str, base_folder: str, exam: dict):
        self.root = Path(vault_path).expanduser()
        if not self.root.exists():
            raise FileNotFoundError(f"No existe el vault: {self.root}")
        self.base = self.root / base_folder
        self.exam = exam
        self.modules_dir = self.base / "Módulos"
        self.concepts_dir = self.base / "Conceptos"
        self.state_dir = self.base / ".study-agent"
        for d in (self.modules_dir, self.concepts_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.index_file = self.state_dir / "index.json"
        self.code = exam["code"]
        self.tag = slugify(self.code)

    # ------------------------------------------------------------ helpers
    def _skill(self, domain_id: str, skill_id: str) -> tuple[dict, dict]:
        for d in self.exam["domains"]:
            if d["id"] == domain_id:
                for s in d["skills"]:
                    if s["id"] == skill_id:
                        return d, s
                return d, {"id": skill_id, "name": skill_id}
        for d in self.exam["domains"]:  # el modelo pudo equivocar el dominio pero no la habilidad
            for s in d["skills"]:
                if s["id"] == skill_id:
                    return d, s
        return {"id": domain_id, "name": domain_id, "weight": "?"}, {"id": skill_id, "name": skill_id}

    @staticmethod
    def _frontmatter(path: Path) -> dict | None:
        """Lee los campos `clave: valor` del frontmatter de una nota existente."""
        if not path.exists():
            return None
        m = re.match(r"---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
        if not m:
            return {}
        return {k.strip(): v.strip() for k, _, v in
                (ln.partition(":") for ln in m.group(1).splitlines()) if v}

    # ------------------------------------------------------------ módulo
    def write_module(self, module, analysis: dict, study: dict, practice: dict) -> Path:
        domain, skill = self._skill(analysis["dominio_id"], analysis["habilidad_id"])
        concepts = analysis["conceptos"]
        concept_names = {c["nombre"] for c in concepts}
        title = module.title or module.slug
        note_name = safe_name(title)
        previous = self._frontmatter(self.modules_dir / f"{note_name}.md")
        if previous and previous.get("fuente") != module.url:  # otro módulo con el mismo título
            note_name = safe_name(f"{title} ({module.slug})")
            previous = self._frontmatter(self.modules_dir / f"{note_name}.md")
        estado = (previous or {}).get("estado", "por-repasar")
        deck = f"flashcards/{self.tag}/{slugify(title)[:40]}"
        today = date.today().isoformat()

        fm = [
            "---",
            "tipo: modulo",
            f"examen: {self.code}",
            f"dominio: {yaml_str(domain['name'])}",
            f"habilidad: {yaml_str(skill['name'])}",
            f"relevancia: {analysis.get('relevancia_examen', 'media')}",
            f"fuente: {module.url}",
            *( [f"ruta: {yaml_str(module.path_title)}"] if module.path_title else [] ),
            *( [f"learn_uid: {module.uid}"] if module.uid else [] ),
            f"creado: {today}",
            f"estado: {estado}",
            f"tags: [{self.tag}, {self.tag}/{domain['id']}, {self.tag}/{skill['id']}]",
            "---",
        ]
        body = [
            f"# {title}",
            "",
            f"> [!info] {self.code} · {domain['name']} ({domain.get('weight', '?')})",
            f"> **Habilidad:** {skill['name']}  ",
            f"> **Fuente:** [Microsoft Learn]({module.url})  ",
            f"> **Por qué aquí:** {analysis.get('justificacion', '')}",
            "",
            "## Puntos clave",
            *[f"- {p}" for p in study.get("puntos_clave", [])],
            "",
            "## Resumen",
            study["resumen"].strip(),
            "",
            "## Conceptos clave",
            *self._concept_lines(concepts),
            "",
            "## Mapa conceptual",
            "```mermaid",
            render_mermaid(study["mapa"], concept_names),
            "```",
            "",
            "## Preguntas tipo examen",
            "Responde mentalmente antes de abrir cada respuesta.",
            "",
            *self._question_blocks(practice["preguntas"], concept_names),
            "## Flashcards",
            f"#{deck}",
            "",
            *self._flashcards(practice["flashcards"]),
            "## Unidades de Learn",
            *[f"- [{u.title or u.slug}]({u.url})" for u in module.units],
            "",
        ]
        path = self.modules_dir / f"{note_name}.md"
        path.write_text("\n".join(fm + body), encoding="utf-8")
        self._write_concepts(concepts, note_name, domain, skill)
        self._update_index(module, note_name, domain, skill, len(practice["preguntas"]),
                           len(practice["flashcards"]), len(concepts))
        return path

    @staticmethod
    def _concept_lines(concepts: list[dict]) -> list[str]:
        order = {"alta": 0, "media": 1, "baja": 2}
        out = []
        for c in sorted(concepts, key=lambda c: order.get(c.get("importancia"), 1)):
            star = " ⭐" if c.get("importancia") == "alta" else ""
            out.append(f"- **[[{safe_name(c['nombre'])}]]**{star} — {c['definicion']}")
            if c.get("trampa_examen"):
                out.append(f"  - ⚠️ *Trampa de examen:* {c['trampa_examen']}")
        return out

    @staticmethod
    def _question_blocks(questions: list[dict], concept_names: set[str]) -> list[str]:
        out = []
        labels = string.ascii_uppercase
        tipo_txt = {"opcion_unica": "Opción única", "opcion_multiple": "Selección múltiple",
                    "si_no": "Sí / No", "escenario": "Escenario"}
        for i, q in enumerate(questions, 1):
            out.append(f"> [!question] P{i} · {tipo_txt.get(q['tipo'], q['tipo'])}")
            for ln in q["enunciado"].strip().splitlines():
                out.append(f"> {ln}")
            out.append(">")
            if q["tipo"] == "si_no" and q.get("afirmaciones"):
                for j, a in enumerate(q["afirmaciones"], 1):
                    out.append(f"> {j}. {a['texto']} — ¿Sí / No?")
                answer = " · ".join(f"{j}: **{'Sí' if a['verdadera'] else 'No'}**"
                                    for j, a in enumerate(q["afirmaciones"], 1))
            else:
                for j, opt in enumerate(q.get("opciones", [])):
                    out.append(f"> - **{labels[j]}.** {opt}")
                correct = [labels[k] for k in q.get("correctas", []) if 0 <= k < len(q.get("opciones", []))]
                answer = ", ".join(f"**{c}**" for c in correct) or "—"
            out.append(">")
            out.append("> > [!success]- Ver respuesta")
            out.append(f"> > {answer}")
            out.append("> >")
            for ln in q["explicacion"].strip().splitlines():
                out.append(f"> > {ln}")
            concept = q.get("concepto", "")
            if concept:
                link = f"[[{safe_name(concept)}]]" if concept in concept_names else concept
                out.append("> >")
                out.append(f"> > Concepto: {link}")
            out.append("")
        return out

    @staticmethod
    def _flashcards(cards: list[dict]) -> list[str]:
        out = []
        for c in cards:
            front = " ".join(c["frente"].split()).replace("::", ":")
            back = " ".join(c["reverso"].split()).replace("::", ":")
            out.append(f"{front}::{back}")
            out.append("")
        return out

    # ------------------------------------------------------------ conceptos
    def _write_concepts(self, concepts: list[dict], module_note: str, domain: dict, skill: dict):
        for c in concepts:
            name = safe_name(c["nombre"])
            path = self.concepts_dir / f"{name}.md"
            link = f"- [[{module_note}]]"
            if path.exists():
                text = path.read_text(encoding="utf-8")
                if link not in text:
                    text = text.rstrip() + "\n" + link + "\n"
                    path.write_text(text, encoding="utf-8")
                continue
            related = [f"[[{safe_name(r)}]]" for r in c.get("relacionados", []) if r != c["nombre"]]
            lines = [
                "---",
                "tipo: concepto",
                f"examen: {self.code}",
                f"importancia: {c.get('importancia', 'media')}",
                f"tags: [{self.tag}/concepto, {self.tag}/{skill['id']}]",
                "---",
                f"# {c['nombre']}",
                "",
                c["definicion"],
                "",
            ]
            if c.get("trampa_examen"):
                lines += [f"> [!warning] Trampa de examen", f"> {c['trampa_examen']}", ""]
            if related:
                lines += ["## Relacionado", ", ".join(related), ""]
            lines += ["## Aparece en", link, ""]
            path.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------ índice / MOC
    def _load_index(self) -> dict:
        if self.index_file.exists():
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        return {"modules": {}}

    def _update_index(self, module, note_name, domain, skill, nq, nc, nconcepts):
        idx = self._load_index()
        idx["modules"][module.url] = {
            "note": note_name, "domain": domain["id"], "skill": skill["id"],
            "path_title": module.path_title, "questions": nq, "flashcards": nc,
            "concepts": nconcepts, "date": date.today().isoformat(),
        }
        self.index_file.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_moc(idx)

    def write_moc(self, idx: dict | None = None) -> Path:
        idx = idx or self._load_index()
        mods = list(idx["modules"].values())
        lines = [
            "---",
            "tipo: mapa-de-estudio",
            f"examen: {self.code}",
            f"tags: [{self.tag}]",
            "---",
            f"# {self.code} · {self.exam['name']} — Mapa de estudio",
            "",
            f"> [!abstract] Progreso",
            f"> {len(mods)} módulos procesados · {sum(m['concepts'] for m in mods)} conceptos · "
            f"{sum(m['questions'] for m in mods)} preguntas · {sum(m['flashcards'] for m in mods)} flashcards  ",
            f"> Puntaje mínimo para aprobar: {self.exam.get('passing_score', 700)}",
            "",
            f"Repasa las flashcards con el plugin **Spaced Repetition** (mazo `#flashcards/{self.tag}`).",
            "",
        ]
        for d in self.exam["domains"]:
            lines.append(f"## {d['name']} ({d['weight']})")
            for s in d["skills"]:
                here = [m for m in mods if m["skill"] == s["id"]]  # los id de habilidad son únicos
                mark = "✅" if here else "⬜"
                lines.append(f"### {mark} {s['name']}")
                lines.append(f"*{s.get('details', '')}*")
                lines += [f"- [[{m['note']}]] · {m['concepts']} conceptos, {m['questions']} preguntas"
                          for m in here] or ["- _Pendiente_"]
                lines.append("")
        known = {s["id"] for d in self.exam["domains"] for s in d["skills"]}
        others = [m for m in mods if m["skill"] not in known]
        if others:
            lines += ["## Sin clasificar", *[f"- [[{m['note']}]]" for m in others], ""]
        path = self.base / f"{self.code} - Mapa de estudio.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def render_mermaid(mapa: dict, concept_names: set[str]) -> str:
    """Convierte {central, nodos, relaciones} en un flowchart Mermaid seguro para Obsidian.

    Los nodos cuyo texto coincide con una nota de concepto reciben la clase `internal-link`,
    así son clicables dentro de Obsidian.
    """
    ids: dict[str, str] = {}

    def nid(raw: str) -> str:
        if raw not in ids:  # `a-b` y `a_b` no deben fusionarse en el mismo nodo
            base = "n_" + (re.sub(r"[^A-Za-z0-9_]", "_", raw) or "x")
            uid, i = base, 2
            while uid in ids.values():
                uid, i = f"{base}_{i}", i + 1
            ids[raw] = uid
        return ids[raw]

    def label(s: str) -> str:
        return s.replace('"', "#quot;").replace("\n", " ").strip()

    nodes = {n["id"]: n["etiqueta"] for n in mapa.get("nodos", [])}
    nodes.setdefault("central", mapa.get("central", "Tema"))
    lines = ["flowchart TD"]
    for k, v in nodes.items():
        shape = ('(["', '"])') if k == "central" else ('["', '"]')
        lines.append(f"    {nid(k)}{shape[0]}{label(v)}{shape[1]}")
    for r in mapa.get("relaciones", []):
        a, b = r["desde"], r["hasta"]
        for x in (a, b):
            if x not in nodes:  # el modelo referenció un nodo no declarado
                nodes[x] = x
                lines.append(f'    {nid(x)}["{label(x)}"]')
        lab = label(r.get("etiqueta", ""))
        arrow = f' -->|"{lab}"| ' if lab else " --> "
        lines.append(f"    {nid(a)}{arrow}{nid(b)}")
    note_names = {safe_name(c) for c in concept_names}  # el nombre real del archivo de la nota
    linked = [nid(k) for k, v in nodes.items() if safe_name(v) in note_names]
    lines.append("    classDef central fill:#0078d4,color:#fff,stroke:#005a9e")
    lines.append(f"    class {nid('central')} central")
    if linked:
        lines.append(f"    class {','.join(linked)} internal-link")
    return "\n".join(lines)
