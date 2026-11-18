#!/bin/bash
# API do RAG no Mac, publicada pelo ngrok. Segredos ficam no backend.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:$PATH"
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  printf 'Use este iniciador no Mac com chip Apple, sem Rosetta.\n'
  exit 1
fi
if [ ! -x backend/.venv/bin/python ] || ! command -v ngrok >/dev/null; then
  printf 'Prepare backend/.venv e instale ngrok. Siga docs/servir-no-mac.md.\n'
  exit 1
fi
# Evita suspensão por ociosidade enquanto este processo estiver aberto.
exec /usr/bin/caffeinate -i backend/.venv/bin/python backend/scripts/servir_ngrok.py "$@"
