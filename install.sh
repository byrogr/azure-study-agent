#!/bin/sh
# Instalador de study-agent para macOS y Linux.
#   curl -fsSL https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.sh | sh
#
# Variables opcionales:
#   STUDY_AGENT_VERSION      versión a instalar, p. ej. v0.2.0 (por defecto, la última)
#   STUDY_AGENT_INSTALL_DIR  carpeta destino (por defecto ~/.local/bin)
#   STUDY_AGENT_BASE_URL     origen de los binarios (por defecto, GitHub Releases)
set -eu

REPO="byrogr/azure-study-agent"
VERSION="${STUDY_AGENT_VERSION:-latest}"
INSTALL_DIR="${STUDY_AGENT_INSTALL_DIR:-$HOME/.local/bin}"

fail() { echo "error: $*" >&2; exit 1; }

case "$(uname -s)" in
  Darwin) os=macos ;;
  Linux)  os=linux ;;
  *) fail "sistema no soportado: $(uname -s). En Windows usa install.ps1." ;;
esac
case "$(uname -m)" in
  x86_64 | amd64)  arch=x64 ;;
  arm64 | aarch64) arch=arm64 ;;
  *) fail "arquitectura no soportada: $(uname -m)" ;;
esac
asset="study-agent-$os-$arch"

if [ -n "${STUDY_AGENT_BASE_URL:-}" ]; then
  base="$STUDY_AGENT_BASE_URL"
elif [ "$VERSION" = latest ]; then
  base="https://github.com/$REPO/releases/latest/download"
else
  base="https://github.com/$REPO/releases/download/$VERSION"
fi

command -v curl >/dev/null 2>&1 || fail "se necesita curl"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Descargando $asset ($VERSION)…"
curl -fsSL "$base/$asset" -o "$tmp/study-agent" || fail "no se pudo descargar $base/$asset"
if curl -fsSL "$base/$asset.sha256" -o "$tmp/sum" 2>/dev/null; then
  expected="$(cut -d' ' -f1 < "$tmp/sum")"
  if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$tmp/study-agent" | cut -d' ' -f1)"
  else actual="$(shasum -a 256 "$tmp/study-agent" | cut -d' ' -f1)"; fi
  [ "$expected" = "$actual" ] || fail "checksum SHA-256 incorrecto"
fi

mkdir -p "$INSTALL_DIR"
chmod +x "$tmp/study-agent"
mv "$tmp/study-agent" "$INSTALL_DIR/study-agent"
echo "✅ Instalado: $INSTALL_DIR/study-agent ($("$INSTALL_DIR/study-agent" --version))"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) echo
     echo "⚠️  $INSTALL_DIR no está en tu PATH. Añade esta línea a ~/.zshrc o ~/.bashrc:"
     echo "    export PATH=\"$INSTALL_DIR:\$PATH\"" ;;
esac

if ! command -v claude >/dev/null 2>&1; then
  echo
  echo "⚠️  Falta Claude Code, que study-agent usa con tu suscripción. Instálalo e inicia sesión:"
  echo "    curl -fsSL https://claude.ai/install.sh | bash && claude"
fi
echo
echo "Siguiente paso: study-agent init"
