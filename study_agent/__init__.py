"""Agente de estudio para certificaciones Azure: Microsoft Learn -> Obsidian."""
import warnings

# El Python de macOS usa LibreSSL y urllib3 avisa en cada ejecución; no afecta a HTTPS con Learn.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

__version__ = "0.1.1"
