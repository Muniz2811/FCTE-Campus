"""Reabre o índice em outro processo, confere os vetores e consulta sem reingerir."""
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from rag.config import carregar_config, caminho_projeto
from rag.armazenamento.embeddings import validar_vetores
from rag.armazenamento.indexacao import abrir_indice
from rag.armazenamento.manifesto import hash_bytes


def main():
    config = carregar_config()
    try:
        indice, manifesto = abrir_indice(config)
        arquivo = caminho_projeto(manifesto['vetores']['arquivo'])
        if hash_bytes(arquivo.read_bytes()) != manifesto['vetores']['sha256']:
            raise ValueError('SHA-256 dos vetores difere do manifesto')
        with np.load(arquivo, allow_pickle=False) as cache:
            vetores = validar_vetores(cache['vetores'], manifesto['indice']['total'], config['embeddings']['dimensao'])
            ids = cache['ids'].tolist()
        if set(indice.colecao.get(include=[])['ids']) != set(ids):
            raise ValueError('IDs do banco diferem dos vetores persistidos')
        hoje = datetime.now(ZoneInfo(config['aquisicao']['fuso_horario'])).date().isoformat()
        resultados = indice.consultar(vetores[0], 5, hoje)
        confirmado = any(r['chunk_id'] == ids[0] and abs(r['distancia']) < 1e-5 for r in resultados)
        if not confirmado:
            raise ValueError('Autoconsulta do vetor persistido não recuperou o chunk esperado')
        print(json.dumps({'reaberto_sem_ingestao': True, 'fontes': manifesto['corpus']['total_fontes'],
                          'chunks': indice.contar(), 'dimensao': config['embeddings']['dimensao'],
                          'vetores_finitos_normalizados': True, 'autoconsulta_confirmada': confirmado,
                          'chunk_conferido': ids[0], 'colecao': manifesto['indice']['colecao']},
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as erro:
        print(f'Conferência falhou: {erro}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
