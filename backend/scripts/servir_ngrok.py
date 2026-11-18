"""Publica somente a integração do RAG do Mac por ngrok, mantendo o contrato existente."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
CAMPOS_BASE = ('GEMINI_API_KEY', 'GEMINI_MODEL', 'RAG_INDEX_BACKEND', 'SUPABASE_URL', 'SUPABASE_SECRET_KEY')


def url_publica(valor):
    p = urlsplit(valor.strip())
    if (p.scheme != 'https' or not p.hostname or p.username or p.password or p.port
            or p.path not in ('', '/') or p.query or p.fragment):
        raise ValueError('Use a URL HTTPS base atribuída pelo ngrok, sem /perguntar ou outros caminhos.')
    if not any(p.hostname.endswith('.' + s) for s in ('ngrok-free.app', 'ngrok-free.dev', 'ngrok.app', 'ngrok.dev')):
        raise ValueError('Informe o dev domain atribuído à sua conta ngrok.')
    return 'https://' + p.hostname


def gravar_privado(caminho, valores):
    # open com 0600 desde a criação; não há janela com permissão pública.
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(caminho, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        for nome, valor in valores.items():
            texto = str(valor).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            f.write(f'{nome}="{texto}"\n')


def preparar_configuracao(url=None, arquivo=None, base=None):
    arquivo = arquivo or BACKEND / '.env.ngrok'
    base = base or BACKEND / '.env'
    existente = dotenv_values(arquivo) if arquivo.is_file() else {}
    valores = {**dotenv_values(base), **existente}
    publica = url_publica(url or valores.get('RAG_PUBLIC_URL') or '')
    cfg = {n: os.environ.get(n) or valores.get(n) or '' for n in CAMPOS_BASE}
    if not cfg['GEMINI_API_KEY'].strip():
        raise ValueError('Preencha GEMINI_API_KEY em backend/.env antes de iniciar.')
    cfg['RAG_INDEX_BACKEND'] = cfg['RAG_INDEX_BACKEND'] or 'chroma'
    if cfg['RAG_INDEX_BACKEND'] not in {'chroma', 'supabase'}:
        raise ValueError('RAG_INDEX_BACKEND deve ser chroma ou supabase.')
    token = os.environ.get('RAG_API_TOKEN') or existente.get('RAG_API_TOKEN') or secrets.token_urlsafe(48)
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('RAG_API_TOKEN precisa ter 32+ caracteres ASCII, sem espaços.')
    cfg.update(RAG_PUBLIC_URL=publica, RAG_PROFILE='full', RAG_REQUIRE_AUTH='true', RAG_API_ONLY='true',
               RAG_API_TOKEN=token, RAG_ALLOWED_HOSTS=f'127.0.0.1,localhost,[::1],{urlsplit(publica).hostname}',
               RAG_ALLOWED_ORIGINS=publica)
    gravar_privado(arquivo, cfg)
    destino = arquivo.with_name('.env.coleta-ngrok')
    gravar_privado(destino, {'G09_API_URL': publica, 'G09_API_TOKEN': token, 'G09_TIMEOUT_SECONDS': '120'})
    return cfg, arquivo, destino


def aguardar_api(processo, porta, token):
    limite = time.monotonic() + 600
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < limite:
            if processo.poll() is not None:
                raise RuntimeError('A API encerrou antes de ficar pronta. Confira a mensagem acima.')
            try:
                r = client.get(f'http://127.0.0.1:{porta}/api/v1/health')
                if r.status_code == 503:
                    raise RuntimeError('O RAG não abriu o índice. Execute este iniciador com --preparar e confira o backend.')
                r.raise_for_status()
                info = r.json()
                if not info.get('vectorSearchEnabled') or not info.get('rerankerEnabled'):
                    raise RuntimeError('O serviço não abriu o perfil completo com E5 e reranker.')
                base = f'http://127.0.0.1:{porta}'
                consultas = ('/perguntar', '/api/v1/multiagent')
                protegido = all(client.post(base + caminho, json={}).status_code == 401
                    and client.post(base + caminho, json={}, headers={'Authorization': f'Bearer {token}'}).status_code == 422
                    for caminho in consultas)
                if not protegido or client.post(base + '/api/v1/chat', json={}).status_code != 404:
                    raise RuntimeError('A API não confirmou o token e o modo somente integração; o túnel não será aberto.')
                return info
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(1)
    raise RuntimeError('O RAG não ficou pronto em dez minutos; o túnel não foi aberto.')


def parar(processo):
    if processo is not None and processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='URL HTTPS do dev domain da sua conta ngrok; necessária na primeira vez')
    parser.add_argument('--port', type=int, default=8001, choices=range(1024, 65536), metavar='PORTA')
    parser.add_argument('--configurar', action='store_true', help='gerar a configuração privada, sem iniciar ou expor a API')
    parser.add_argument('--preparar', action='store_true', help='preparar modelos e conferir o índice antes de iniciar')
    args = parser.parse_args()
    api = tunel = None
    try:
        cfg, arquivo, render = preparar_configuracao(args.url)
        print(f'Configuração privada: {arquivo}\nVariáveis para importar no Render da coleta: {render}', flush=True)
        if args.configurar:
            return 0
        ngrok = shutil.which('ngrok')
        if not ngrok:
            raise RuntimeError('Instale ngrok: brew install ngrok. Depois configure o authtoken da conta.')
        # Nunca encerrar um servidor que já ocupa esta porta.
        with socket.socket() as teste:
            teste.bind(('127.0.0.1', args.port))
        env = {**os.environ, **cfg, 'RAG_ENV_FILE': str(arquivo), 'PYTHONIOENCODING': 'utf-8'}
        if args.preparar:
            comandos = [['scripts/preparar_modelos.py', '--incluir-e5']]
            if cfg['RAG_INDEX_BACKEND'] == 'chroma':
                comandos.append(['scripts/05_indexar.py'])
            comandos.append(['scripts/06_conferir.py'])
            for comando in comandos:
                subprocess.run([sys.executable, *comando], cwd=BACKEND, env=env, check=True)
        api = subprocess.Popen([sys.executable, 'scripts/servir.py', '--port', str(args.port)], cwd=BACKEND, env=env)
        info = aguardar_api(api, args.port, cfg['RAG_API_TOKEN'])
        # A API já está pronta antes de abrir a conexão pública. Não inspecionar corpos/tokens no agente.
        tunel = subprocess.Popen([ngrok, 'http', f'http://127.0.0.1:{args.port}', '--url', cfg['RAG_PUBLIC_URL'],
                                  '--inspect=false', '--log=stdout'])
        print(f'\nRAG completo pronto: {info["sources"]} fontes, {info["chunks"]} chunks.\n'
              f'Endereço configurado no túnel: {cfg["RAG_PUBLIC_URL"]}\n'
              'Aguarde o ngrok confirmar a conexão. Deixe o Mac ligado e a tampa aberta. Control+C encerra API e túnel.\n', flush=True)
        while api.poll() is None and tunel.poll() is None:
            time.sleep(1)
        raise RuntimeError('A API ou o túnel encerrou. Confira o log acima; nenhum outro servidor foi encerrado.')
    except KeyboardInterrupt:
        print('\nEncerrando somente a API e o túnel iniciados aqui.', flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, httpx.HTTPError) as erro:
        print(f'Não foi possível servir o RAG: {erro}', file=sys.stderr)
        return 1
    finally:
        parar(tunel)
        parar(api)


def interromper(*_):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interromper)
    raise SystemExit(main())
