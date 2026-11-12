"""BM25 e fusão RRF para o pequeno corpus local, sem outro serviço ou modelo."""
import math
import re
import unicodedata
from collections import Counter

IGNORAR = frozenset('a ao aos as o os e ou de da das do dos em na nas no nos um uma uns umas '
                   'para por com sem que qual quais como onde quando quanto quantas quantos '
                   'se eu voce voces me meu minha seus suas seu sua isso esse essa esses essas '
                   'este esta estes estas neste nesta nesse nessa ha tem sao ser fica ficam '
                   'sobre tambem agora'.split())


def termos(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold())
                    if not unicodedata.combining(c))
    return [t for t in re.findall(r'[a-z0-9]+', texto) if len(t) > 1 and t not in IGNORAR]


def ordenar_bm25(pergunta, trechos, k1, b):
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError('Parâmetros BM25 inválidos')
    documentos = [Counter(termos(t['texto'])) for t in trechos]
    consultas = set(termos(pergunta))
    total = len(documentos)
    media = sum(sum(d.values()) for d in documentos) / total if total else 0
    frequencias = Counter(t for d in documentos for t in d)
    resultados = []
    for trecho, documento in zip(trechos, documentos):
        tamanho, score = sum(documento.values()), 0.0
        for termo in consultas:
            tf = documento[termo]
            if not tf:
                continue
            idf = math.log(1 + (total - frequencias[termo] + .5) / (frequencias[termo] + .5))
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * tamanho / media))
        if score > 0:
            resultados.append(dict(trecho, score_bm25=score))
    return sorted(resultados, key=lambda t: (-t['score_bm25'], t['chunk_id']))


def fundir_rrf(densos, lexicais, constante):
    if constante <= 0:
        raise ValueError('Constante RRF precisa ser positiva')
    scores, trechos = Counter(), {}
    for nome, ranking in (('denso', densos), ('lexical', lexicais)):
        for posicao, trecho in enumerate(ranking, 1):
            cid = trecho['chunk_id']
            scores[cid] += 1 / (constante + posicao)
            trechos.setdefault(cid, {}).update(trecho)
            trechos[cid][f'rank_{nome}'] = posicao
    return [dict(trechos[cid], score_rrf=scores[cid])
            for cid in sorted(scores, key=lambda cid: (-scores[cid], trechos[cid]['distancia'], cid))]
