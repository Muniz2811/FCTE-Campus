"""Importa UAC/UED da coleta; não chama Gemini, não publica nem altera o mapa."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import carregar_config
from rag.ingestao.mapas import importar_mapas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coleta', type=Path, required=True, help='Raiz do repositório coleta-fcte')
    parser.add_argument('--data', type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    resultado = importar_mapas(args.coleta, carregar_config(), args.data.isoformat())
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
