"""Lectura de contenido de Microsoft Learn: rutas, módulos y unidades.

Microsoft Learn expone el Markdown limpio de cada página con `?accept=text/markdown`.
Para descubrir módulos (en una ruta) y unidades (en un módulo) se usa el HTML.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

import requests

BASE = "https://learn.microsoft.com"
UA = "azure-study-agent/1.0 (+personal study tool)"

_LOCALE_RE = re.compile(r"^/([a-z]{2}-[a-z]{2})/")


@dataclass
class Unit:
    url: str
    slug: str
    title: str = ""
    markdown: str = ""


@dataclass
class Module:
    url: str
    slug: str
    title: str = ""
    uid: str = ""
    path_title: str = ""
    units: list[Unit] = field(default_factory=list)

    @property
    def content(self) -> str:
        parts = []
        for u in self.units:
            parts.append(f"\n\n## [Unidad] {u.title}\nFuente: {u.url}\n\n{u.markdown}")
        return f"# {self.title}\n" + "".join(parts)


class LearnClient:
    def __init__(self, locale: str = "es-es", session: requests.Session | None = None):
        self.locale = locale
        self.http = session or requests.Session()
        self.http.headers["User-Agent"] = UA

    # ---------- utilidades de URL ----------
    def normalize(self, url: str) -> str:
        """Fuerza el idioma configurado y quita query/fragment."""
        p = urlparse(url if url.startswith("http") else BASE + url)
        path = p.path
        if _LOCALE_RE.match(path):
            path = _LOCALE_RE.sub(f"/{self.locale}/", path, count=1)
        else:
            path = f"/{self.locale}{path}"
        return urlunparse(("https", "learn.microsoft.com", path, "", "", ""))

    @staticmethod
    def kind(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        if "/training/paths/" in path:
            return "path"
        m = re.search(r"/training/modules/([^/]+)(/([^/]+))?$", path)
        if m:
            return "unit" if m.group(3) else "module"
        raise ValueError(f"URL no reconocida como ruta, módulo o unidad de Learn: {url}")

    # ---------- HTTP ----------
    def _get(self, url: str, markdown: bool = False) -> str:
        target = url + ("?accept=text/markdown" if markdown else "")
        r = self.http.get(target, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"  # sin charset, requests asumiría ISO-8859-1 para text/*
        return r.text

    # ---------- descubrimiento ----------
    @staticmethod
    def _title_from_html(html: str) -> str:
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html) or \
            re.search(r"<title>([^<]+)</title>", html)
        t = m.group(1) if m else ""
        return re.sub(r"\s*-\s*Training(\s*\|.*)?$|\s*\|\s*Microsoft Learn$", "", t).strip()

    @staticmethod
    def _meta(html: str, name: str) -> str:
        m = re.search(rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"', html)
        return m.group(1) if m else ""

    def list_modules(self, path_url: str) -> tuple[str, list[str]]:
        html = self._get(path_url)
        title = self._title_from_html(html)
        # Absolutos (/es-es/training/modules/x/) o relativos a la ruta (../../modules/x/)
        link_re = re.compile(r'href="(?:(?:https://learn\.microsoft\.com)?(?:/[a-z]{2}-[a-z]{2})?/training/|(?:\.\./)+)'
                             r'modules/([a-z0-9-]+)/?"')
        links = list(link_re.finditer(html))
        # Los prerrequisitos pueden enlazar otros módulos: la lista real de la ruta va
        # después del encabezado "Módulos en esta ruta" / "Modules in this learning path".
        start = 0
        if links:
            heads = [m.start() for m in re.finditer(r"<h2\b[^>]*>(.*?)</h2>", html, re.S)
                     if re.search(r"(?i)m[óo]dul", re.sub(r"<[^>]+>", "", m.group(1)))
                     and m.start() < links[-1].start()]
            start = heads[-1] if heads else 0
        slugs: list[str] = []
        for m in (x for x in links if x.start() > start):
            if m.group(1) not in slugs:
                slugs.append(m.group(1))
        return title, [f"{BASE}/{self.locale}/training/modules/{s}/" for s in slugs]

    def load_module(self, module_url: str, skip: list[str] | None = None, path_title: str = "",
                    fetch_units: bool = True) -> Module:
        module_url = self.normalize(module_url).rstrip("/") + "/"
        slug = urlparse(module_url).path.rstrip("/").split("/")[-1]
        html = self._get(module_url)
        mod = Module(url=module_url, slug=slug, title=self._title_from_html(html),
                     uid=self._meta(html, "uid"), path_title=path_title)
        pat = re.compile(
            # Absolutos o relativos al módulo (href="1-introduction", como sirve Learn hoy)
            rf'href="(?:(?:https://learn\.microsoft\.com)?(?:/[a-z]{{2}}-[a-z]{{2}})?/training/modules/{re.escape(slug)}/)?'
            rf'([0-9]+[a-z]?-[a-z0-9-]+)/?"[^>]*>(.*?)</a>',
            re.S,
        )
        seen = set()
        for m in pat.finditer(html):
            uslug = m.group(1)
            if uslug in seen:
                continue
            seen.add(uslug)
            if skip and any(s in uslug for s in skip):
                continue
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            mod.units.append(Unit(url=f"{module_url}{uslug}", slug=uslug, title=title))
        if fetch_units:
            for u in mod.units:
                self.fill_unit(u)
        return mod

    def load_single_unit(self, unit_url: str) -> Module:
        unit_url = self.normalize(unit_url)
        parts = urlparse(unit_url).path.rstrip("/").split("/")
        u = Unit(url=unit_url, slug=parts[-1])
        self.fill_unit(u)
        return Module(url=unit_url, slug=f"{parts[-2]}--{parts[-1]}", title=u.title, units=[u])

    def fill_unit(self, unit: Unit) -> None:
        raw = self._get(unit.url, markdown=True)
        if raw.lstrip().startswith("<"):
            raw = html_to_markdown(raw)
        md, title = clean_unit_markdown(raw)
        unit.markdown = md
        unit.title = unit.title or title


def html_to_markdown(html: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.body or soup
    for tag in main.select("script, style, nav, button, form, footer, [data-bi-name='feedback']"):
        tag.decompose()
    return markdownify(str(main), heading_style="ATX")


_NOISE = [
    re.compile(r"^\s*(Completado|Completed)\s*$", re.I),
    re.compile(r"^\s*-\s*\d+\s*(minutos?|minutes?)\s*$", re.I),
    # asistente de ejemplo "Pregunte a Anton" que aparece en cada módulo
    re.compile(r"\b(Pregunt[ae]|Ask)\s+(a\s+)?Anton\b|choose-anton", re.I),
]


def clean_unit_markdown(raw: str) -> tuple[str, str]:
    """Quita frontmatter, bloques de vídeo y ruido de UI. Devuelve (markdown, título)."""
    text = raw
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    # Learn tiene pivotes vídeo/texto: nos quedamos con el texto.
    text = re.sub(r'::: zone pivot="video".*?::: zone-end', "", text, flags=re.S)
    text = re.sub(r"^:::.*$", "", text, flags=re.M)
    lines = [ln for ln in text.splitlines() if not any(p.search(ln) for p in _NOISE)]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    m = re.search(r"^#\s+(.+)$", text, re.M)
    title = m.group(1).strip() if m else ""
    return text, title
