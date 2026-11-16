#!/bin/bash
# Iniciador local para macOS Apple Silicon. Não instala ferramentas do sistema.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
on_error() {
  printf '\nNão foi possível concluir. Confira a mensagem acima.\n'
  if [ -t 0 ]; then read -r -p 'Pressione Enter para fechar… ' _reply; fi
}
trap cleanup EXIT
trap on_error ERR
trap 'exit 130' INT TERM

if [ "$(uname -s)" != 'Darwin' ] || [ "$(uname -m)" != 'arm64' ]; then
  printf 'Este iniciador é para Macs com chip Apple e Terminal nativo (sem Rosetta).\n'
  exit 1
fi

# O Finder não carrega o mesmo PATH de um terminal configurado pelo usuário.
export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:$PATH"
if ! command -v node >/dev/null || ! command -v npm >/dev/null || ! command -v python3.12 >/dev/null; then
  printf '\nPrimeiro, instale Node e Python uma única vez.\n'
  printf 'Com Homebrew instalado (https://brew.sh), execute:\n\n'
  printf '  brew install node@22 python@3.12\n\n'
  printf 'Depois abra iniciar.command novamente.\n'
  on_error
  exit 1
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("Use Node 22.12 ou superior."); process.exit(1); }'
python3.12 -c 'import platform, sys; sys.exit(0 if platform.machine() == "arm64" else "Use Python nativo arm64, sem Rosetta.")'

printf '\nFCTE Campus — preparando seu assistente\n'
printf 'A primeira execução baixa dependências e modelos; pode demorar.\n\n'

if [ ! -x backend/.venv/bin/python ]; then
  python3.12 -m venv backend/.venv
fi
PYTHON="$ROOT/backend/.venv/bin/python"
"$PYTHON" -c 'import platform, sys; sys.exit(0 if platform.machine() == "arm64" and sys.version_info[:2] == (3, 12) else "O ambiente backend/.venv deve ter sido criado neste Mac com Python 3.12 arm64. Consulte o README.")'
mkdir -p .cache/launcher

# Marcadores só são gravados após sucesso. Mudanças nos arquivos refazem a etapa.
fingerprint() {
  "$PYTHON" - "$1" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path.cwd()
groups = {
    'python': ['backend/requirements.txt'],
    'npm': ['package.json', 'package-lock.json'],
    'index': ['backend/config/rag.yaml', 'backend/data/catalogo/fontes.csv',
              'backend/data/chunks/chunks.jsonl', 'backend/requirements.txt',
              'backend/rag/armazenamento', 'backend/scripts/preparar_modelos.py'],
    'web': ['src', 'public', 'index.html', 'package.json', 'package-lock.json',
            'tsconfig.json', 'vite.config.ts'],
}
files = []
for name in groups[sys.argv[1]]:
    path = root / name
    if path.is_dir():
        files.extend(p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and p.name != '.DS_Store')
    else:
        files.append(path)
digest = hashlib.sha256()
for path in sorted(files):
    digest.update(str(path.relative_to(root)).encode())
    digest.update(b'\0')
    digest.update(path.read_bytes())
print(digest.hexdigest())
PY
}
changed() { [ ! -f "$1" ] || [ "$(cat "$1")" != "$2" ]; }

PY_HASH="$(fingerprint python)"
if changed backend/.venv/.fcte-requirements "$PY_HASH"; then
  printf 'Instalando as dependências do RAG…\n'
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r backend/requirements.txt
  "$PYTHON" -m pip check
  printf '%s' "$PY_HASH" > backend/.venv/.fcte-requirements
fi

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
if ! "$PYTHON" -c 'import os, sys; from dotenv import dotenv_values; sys.exit(0 if (os.getenv("GEMINI_API_KEY") or dotenv_values("backend/.env").get("GEMINI_API_KEY") or "").strip() else 1)'; then
  printf '\nFalta configurar sua chave Gemini. Vou abrir backend/.env no editor.\n'
  printf 'Preencha GEMINI_API_KEY e salve o arquivo. Não envie esse arquivo ao GitHub.\n'
  open -e "$ROOT/backend/.env"
  read -r -p 'Depois de salvar, pressione Enter aqui para continuar… ' _reply
  "$PYTHON" -c 'import os, sys; from dotenv import dotenv_values; sys.exit(0 if (os.getenv("GEMINI_API_KEY") or dotenv_values("backend/.env").get("GEMINI_API_KEY") or "").strip() else "A chave ainda está vazia em backend/.env.")'
fi

NPM_HASH="$(fingerprint npm)-$(node --version)-$(node -p 'process.arch')"
if [ ! -d node_modules ] || changed node_modules/.fcte-dependencies "$NPM_HASH"; then
  printf '\nInstalando as dependências da interface…\n'
  npm ci
  printf '%s' "$NPM_HASH" > node_modules/.fcte-dependencies
fi

INDEX_HASH="$(fingerprint index)"
INDEX_BACKEND="$("$PYTHON" -c 'import sys; sys.path.insert(0, "backend"); from rag.config import carregar_config; print(carregar_config()["indice"]["backend"])')"
if [ "$INDEX_BACKEND" = 'supabase' ]; then
  printf '\nConferindo o banco Supabase (sem publicar dados)…\n'
  if [ ! -f backend/.cache/reranker/revision.txt ]; then npm run rag:prepare; fi
  npm run rag:check
elif [ ! -f backend/data/index/manifesto.json ] || [ ! -d backend/data/index/chroma ] ||
   [ ! -f backend/.cache/reranker/revision.txt ] || changed .cache/launcher/index "$INDEX_HASH"; then
  printf '\nPreparando os modelos e o banco vetorial…\n'
  npm run rag:prepare
  npm run rag:index
  npm run rag:check
  printf '%s' "$INDEX_HASH" > .cache/launcher/index
fi

WEB_HASH="$(fingerprint web)-$NPM_HASH"
if [ ! -f dist/index.html ] || changed .cache/launcher/web "$WEB_HASH"; then
  printf '\nPreparando a interface…\n'
  npm run build
  printf '%s' "$WEB_HASH" > .cache/launcher/web
fi

if lsof -nP -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  printf '\nA porta 8001 já está em uso. Encerre o servidor anterior com Control + C.\n'
  printf 'Nenhum processo existente foi encerrado por este iniciador.\n'
  on_error
  exit 1
fi

printf '\nIniciando o sistema em http://127.0.0.1:8001…\n'
"$PYTHON" backend/scripts/servir.py &
SERVER_PID=$!
READY=0
for ((attempt=0; attempt<180; attempt++)); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    printf '\nO servidor encerrou antes de ficar pronto.\n'
    on_error
    exit 1
  fi
  if curl --fail --silent --max-time 2 http://127.0.0.1:8001/api/v1/health >/dev/null; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" != 1 ]; then
  printf '\nO RAG não ficou disponível. Confira o erro do backend acima e o README.\n'
  on_error
  exit 1
fi
open http://127.0.0.1:8001
printf '\nPronto! O navegador foi aberto.\n'
printf 'Deixe este terminal aberto. Para encerrar o sistema, pressione Control + C.\n\n'
wait "$SERVER_PID"
