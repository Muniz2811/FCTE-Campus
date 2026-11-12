"""Mostra e registra evidências recuperadas. Nesta etapa não chama Gemini."""
import argparse
import json
import sys
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.consulta.busca import buscar
from rag.config import carregar_config, configurar_cache, caminho_projeto
from rag.armazenamento.manifesto import gravar_json


def main():
    parser = argparse.ArgumentParser(description='Consulta semântica das fontes aprovadas, sem LLM.')
    parser.add_argument('pergunta')
    parser.add_argument('--json', action='store_true', help='imprimir a execução completa em JSON')
    args = parser.parse_args()
    config = carregar_config()
    configurar_cache(config)
    try:
        resultado = buscar(args.pergunta, config)
    except (ValueError, OSError) as erro:
        print(f'Consulta não executada: {erro}', file=sys.stderr)
        return 1
    nome = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'
    arquivo = caminho_projeto(config['caminhos']['execucoes']) / nome
    gravar_json(arquivo, resultado)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print('Pergunta:', resultado['pergunta'])
        print(f"Base: {resultado['corpus_fontes']} fontes | {resultado['colecao']}")
        for trecho in resultado['trechos']:
            print(f"\n{trecho['posicao']}. {trecho['chunk_id']} | {trecho['source_id']} | distância {trecho['distancia']:.6f}")
            print(trecho['titulo'], '|', ' > '.join(trecho['secoes']))
            print(trecho['texto'])
            print(f"Fonte: {trecho['url']} | versão {trecho['versao']} | revisão {trecho['data_revisao']} | validade {trecho['validade']}")
        print('\n' + resultado['limite'])
        print('Registro:', arquivo.relative_to(caminho_projeto('.')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
