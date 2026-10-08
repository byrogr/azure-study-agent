"""Wrapper de Claude Code en modo headless (`claude -p`).

Usa la sesión con la que iniciaste Claude Code, es decir, tu suscripción de Claude
(Pro/Max), sin API key. Cada llamada corre sin herramientas, sin cargar CLAUDE.md ni
settings del proyecto y sin guardar la sesión en el historial.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile


class LLMError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = True):
        super().__init__(msg)
        self.retryable = retryable


_LIMIT_RE = re.compile(r"(?i)usage limit|limit reached|rate.?limit|quota|credit balance|overloaded")


class ClaudeCLI:
    def __init__(self, bin: str = "claude", model: str = "sonnet", timeout: int = 900,
                 use_json_schema: bool = True):
        self.bin = shutil.which(bin) or bin
        self.model = model
        self.timeout = timeout
        self.use_json_schema = use_json_schema
        self.calls = 0
        self.cost_usd = 0.0

    def check(self) -> None:
        if not shutil.which(self.bin) and not os.path.exists(self.bin):
            raise LLMError(
                "No encuentro el CLI `claude`. Instálalo (npm i -g @anthropic-ai/claude-code) "
                "y ejecuta `claude` una vez para iniciar sesión con tu cuenta.")

    def ask_json(self, system: str, prompt: str, schema: dict | None = None, retries: int = 2) -> dict:
        last_err = None
        extra = ""
        for _ in range(retries + 1):
            try:
                return self._call(system, prompt + extra, schema if self.use_json_schema else None)
            except json.JSONDecodeError as e:
                last_err = e
                extra = ("\n\nIMPORTANTE: tu respuesta anterior no era JSON válido. "
                         "Responde SOLO con el objeto JSON, sin texto adicional ni bloques de código.")
            except LLMError as e:
                if not e.retryable:  # límite de uso, timeout...: reintentar solo gasta tiempo
                    raise
                last_err = e
        raise LLMError(f"Claude falló tras {retries + 1} intentos: {last_err}")

    def _call(self, system: str, prompt: str, schema: dict | None) -> dict:
        args = [self.bin, "-p", "--output-format", "json", "--model", self.model,
                "--tools", "", "--no-session-persistence", "--setting-sources", "",
                "--system-prompt", system]
        if schema:
            args += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
        with tempfile.TemporaryDirectory() as cwd:  # aísla de CLAUDE.md del directorio actual
            try:
                proc = subprocess.run(args, input=prompt, capture_output=True, text=True,
                                      timeout=self.timeout, cwd=cwd)
            except subprocess.TimeoutExpired:
                raise LLMError(f"`claude` superó el timeout de {self.timeout}s", retryable=False)
        self.calls += 1
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout).strip()[:800]
            if schema and "json-schema" in msg:
                self.use_json_schema = False  # versión antigua de Claude Code
                return self._call(system, prompt, None)
            raise LLMError(f"`claude` terminó con código {proc.returncode}: {msg}",
                           retryable=not _LIMIT_RE.search(msg))
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            msg = str(envelope.get("result"))[:800]
            raise LLMError(f"Claude respondió con error: {msg}", retryable=not _LIMIT_RE.search(msg))
        self.cost_usd += float(envelope.get("total_cost_usd") or 0)
        structured = envelope.get("structured_output")
        if isinstance(structured, dict):
            return structured
        return extract_json(envelope.get("result", ""))


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("No hay objeto JSON en la respuesta", text, 0)
    return json.loads(text[start:end + 1])
