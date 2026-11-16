"""Reabre o índice em outro processo, confere os vetores e consulta sem reingerir."""
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import carregar_config, caminho_projeto
from rag.armazenamento.leitura import abrir_indice, carregar_base_lexical
from rag.armazenamento.manifesto import hash_bytes


def conferir_lexical(config, indice, manifesto):
    from rag.consulta.busca import buscar, elegiveis_em
    from rag.consulta.busca_lexical import termos
    base = carregar_base_lexical(indice, manifesto, config)
    hoje = datetime.now(ZoneInfo(config['aquisicao']['fuso_horario'])).date().isoformat()
    elegiveis = elegiveis_em(base[0], hoje)
    if not elegiveis:
        raise ValueError('A base não contém textos elegíveis na data atual')
    pergunta = ' '.join(termos(elegiveis[0]['texto'])[:12])
    resultado = buscar(pergunta, config, base_lexical=base)
    ids = {t['chunk_id'] for t in elegiveis}
    if not resultado['trechos'] or any(t['chunk_id'] not in ids or t['score_bm25'] <= 0
                                      for t in resultado['trechos']):
        raise ValueError('Consulta de conferência BM25 não recuperou textos elegíveis')
    return {'perfil': 'light', 'armazenamento': 'supabase', 'metodo': 'bm25',
            'reaberto_sem_ingestao': True, 'fontes': manifesto['corpus']['total_fontes'],
            'chunks': len(base[0]), 'textos_ids_metadados_conferidos': True,
            'consulta_bm25_confirmada': True, 'vetores_verificados_nesta_execucao': False}


def main():
    config = carregar_config()
    try:
        indice, manifesto = abrir_indice(config)
        if config.get('perfil') == 'light':
            print(json.dumps(conferir_lexical(config, indice, manifesto), ensure_ascii=False, indent=2))
            return 0
        import numpy as np
        from rag.armazenamento.embeddings import validar_vetores
        if config['indice'].get('backend') == 'supabase':
            ids, vetores = indice.exportar_vetores()
            validar_vetores(vetores, manifesto['indice']['total'], config['embeddings']['dimensao'])
        else:
            arquivo = caminho_projeto(manifesto['vetores']['arquivo'])
            if hash_bytes(arquivo.read_bytes()) != manifesto['vetores']['sha256']:
                raise ValueError('SHA-256 dos vetores difere do manifesto')
            with np.load(arquivo, allow_pickle=False) as cache:
                vetores = validar_vetores(cache['vetores'], manifesto['indice']['total'], config['embeddings']['dimensao'])
                ids = cache['ids'].tolist()
        if indice.ids() != set(ids):
            raise ValueError('IDs do banco diferem dos vetores persistidos')
        hoje = datetime.now(ZoneInfo(config['aquisicao']['fuso_horario'])).date().isoformat()
        resultados = indice.consultar(vetores[0], 5, hoje)
        confirmado = any(r['chunk_id'] == ids[0] and abs(r['distancia']) < 1e-5 for r in resultados)
        if not confirmado:
            raise ValueError('Autoconsulta do vetor persistido não recuperou o chunk esperado')
        print(json.dumps({'reaberto_sem_ingestao': True, 'fontes': manifesto['corpus']['total_fontes'],
                          'chunks': indice.contar(), 'dimensao': config['embeddings']['dimensao'],
                          'vetores_finitos_normalizados': True, 'autoconsulta_confirmada': confirmado,
                          'chunk_conferido': ids[0], 'colecao': manifesto['indice']['colecao'],
                          'armazenamento': config['indice'].get('backend', 'chroma')},
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as erro:
        print(f'Conferência falhou: {erro}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
