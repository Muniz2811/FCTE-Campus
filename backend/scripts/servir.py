"""Inicia a API local com um worker. Em backend/: python scripts/servir.py --env-file .env"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description='Servidor local do RAG para o FCTE Campus.')
    parser.add_argument('--env-file', help='arquivo .env do backend; apenas a chave Gemini e GEMINI_MODEL são usados')
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    if args.env_file:
        arquivo = Path(args.env_file).resolve()
        if not arquivo.is_file():
            parser.error('Arquivo de ambiente não encontrado')
        os.environ['RAG_ENV_FILE'] = str(arquivo)
    import uvicorn
    uvicorn.run('rag.api:app', host='127.0.0.1', port=args.port, workers=1, access_log=False)


if __name__ == '__main__':
    main()
