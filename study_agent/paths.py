"""Rutas de usuario, configuración y temarios.

  Config:  $STUDY_AGENT_CONFIG_DIR › $XDG_CONFIG_HOME/study-agent
           › %APPDATA%\\study-agent (Windows) › ~/.config/study-agent (macOS/Linux)
  Caché:   $XDG_CACHE_HOME/study-agent
           › %LOCALAPPDATA%\\study-agent\\cache (Windows) › ~/.cache/study-agent (macOS/Linux)
  Temarios propios en <config>/exams/<id>.yaml; si no, los incluidos en el paquete.
"""
from __future__ import annotations

import os
import sys
from importlib.resources import files
from pathlib import Path

import yaml

PACKAGE_DATA = files("study_agent")
PLACEHOLDER = "TU_USUARIO"


class ConfigError(RuntimeError):
    pass


def config_dir() -> Path:
    if os.environ.get("STUDY_AGENT_CONFIG_DIR"):
        return Path(os.environ["STUDY_AGENT_CONFIG_DIR"]).expanduser()
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).expanduser() / "study-agent"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or "~/AppData/Roaming").expanduser() / "study-agent"
    return Path("~/.config/study-agent").expanduser()


def cache_dir() -> Path:
    if os.environ.get("XDG_CACHE_HOME"):
        return Path(os.environ["XDG_CACHE_HOME"]).expanduser() / "study-agent"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or "~/AppData/Local").expanduser() / "study-agent" / "cache"
    return Path("~/.cache/study-agent").expanduser()


def config_template() -> str:
    return PACKAGE_DATA.joinpath("config.example.yaml").read_text(encoding="utf-8")


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def user_config_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if os.environ.get("STUDY_AGENT_CONFIG"):
        return Path(os.environ["STUDY_AGENT_CONFIG"]).expanduser()
    return config_dir() / "config.yaml"


def load_config(explicit: str | None = None) -> dict:
    """Valores por defecto del paquete + config del usuario + STUDY_AGENT_VAULT."""
    cfg = yaml.safe_load(config_template()) or {}
    path = user_config_path(explicit)
    if path.exists():
        cfg = _merge(cfg, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    elif explicit:
        raise ConfigError(f"No existe el archivo de configuración: {path}")
    if os.environ.get("STUDY_AGENT_VAULT"):  # p. ej. en Docker, donde el vault se monta en /vault
        cfg["vault_path"] = os.environ["STUDY_AGENT_VAULT"]
    return cfg


def require_vault(cfg: dict) -> str:
    vault = str(cfg.get("vault_path") or "")
    if not vault or PLACEHOLDER in vault:
        raise ConfigError("No hay vault configurado. Ejecuta `study-agent init` "
                          "(o define STUDY_AGENT_VAULT).")
    return vault


def _exam_files() -> dict[str, object]:
    found = {p.name[:-5]: p for p in PACKAGE_DATA.joinpath("exams").iterdir() if p.name.endswith(".yaml")}
    user = config_dir() / "exams"
    if user.is_dir():
        found.update({p.stem: p for p in user.glob("*.yaml")})  # los propios pisan a los incluidos
    return found


def list_exams() -> dict[str, dict]:
    return {k: yaml.safe_load(v.read_text(encoding="utf-8")) for k, v in sorted(_exam_files().items())}


def load_exam(exam_id: str) -> dict:
    f = _exam_files().get(exam_id)
    if f is None:
        raise ConfigError(f"No existe el temario `{exam_id}`. Disponibles: {', '.join(sorted(_exam_files()))}. "
                          f"Puedes añadir el tuyo en {config_dir() / 'exams'}/<id>.yaml")
    return yaml.safe_load(f.read_text(encoding="utf-8"))
