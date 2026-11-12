"""Recuperação de evidências. Não produz respostas de linguagem natural."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from rag.armazenamento.embeddings import VetorizadorE5
from rag.armazenamento.indexacao import abrir_indice
from rag.consulta.busca_lexical import ordenar_bm25, fundir_rrf


def selecionar_diversos(candidatos: list[dict], top_k: int, max_por_fonte: int) -> list[dict]:
    escolhidos, por_fonte = [], Counter()
    for trecho in candidatos:
        if por_fonte[trecho['source_id']] >= max_por_fonte:
            continue
        escolhidos.append(trecho)
        por_fonte[trecho['source_id']] += 1
        if len(escolhidos) == top_k:
            break
    # Não relaxar o limite para completar cinco com mais trechos da mesma fonte.
    return [dict(t, posicao=i) for i, t in enumerate(escolhidos, 1)]


def buscar(pergunta: str, config: dict, modelo=None) -> dict:
    if not pergunta.strip():
        raise ValueError('Pergunta vazia')
    cfg = config['busca']
    if cfg['top_k'] <= 0 or cfg['max_por_fonte'] <= 0 or cfg['candidatos'] < cfg['top_k']:
        raise ValueError('Parâmetros de busca inválidos')
    indice, manifesto = abrir_indice(config)
    modelo = modelo if modelo is not None else VetorizadorE5(config['embeddings'])
    vetor = modelo.pergunta(pergunta)
    agora = datetime.now(ZoneInfo(config['aquisicao']['fuso_horario']))
    metodo = cfg.get('metodo', 'densa')
    if metodo == 'hibrida_rrf':
        # Corpus local pequeno. Ambos os rankings usam o MESMO conjunto elegível.
        # Em corpus grande, substituir esta leitura por índice lexical persistente.
        elegiveis = indice.consultar(vetor, indice.contar(), agora.date().isoformat())
        lexicais = ordenar_bm25(pergunta, elegiveis, cfg['bm25_k1'], cfg['bm25_b'])
        candidatos = fundir_rrf(elegiveis[:cfg['candidatos']], lexicais[:cfg['candidatos']], cfg['rrf_k'])
    elif metodo == 'densa':
        candidatos = indice.consultar(vetor, cfg['candidatos'], agora.date().isoformat())
    else:
        raise ValueError('Método de busca desconhecido')
    reranker = cfg.get('reranker', {})
    if reranker.get('ativo'):
        from rag.consulta.reranking import reordenar
        candidatos = reordenar(pergunta, candidatos, reranker)
        limiar = reranker.get('limiar')
        if limiar is not None:
            candidatos = [c for c in candidatos if c['score_reranker'] >= limiar]
    escolhidos = selecionar_diversos(candidatos, cfg['top_k'], cfg['max_por_fonte'])
    return {'pergunta': pergunta, 'executado_em': agora.isoformat(timespec='seconds'),
            'etapa': 'recuperacao_sem_geracao', 'assinatura_indice': manifesto['assinatura'],
            'embeddings': manifesto['embeddings'], 'colecao': manifesto['indice']['colecao'],
            'config_busca': cfg, 'candidatos_avaliados': candidatos, 'corpus_fontes': manifesto['corpus']['total_fontes'],
            'trechos': escolhidos,
            'limite': 'Distância cosseno não é probabilidade de verdade. Logit neural e corte experimental não garantem relevância ou verdade; calibração diagnóstica em perguntas conhecidas.'}
