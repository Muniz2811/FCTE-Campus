"""Relevância pergunta–trecho, após a recuperação híbrida e antes da seleção."""
from functools import lru_cache
import numpy as np

from rag.config import caminho_projeto


class Reranker:
    def __init__(self, config):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.config = config
        local = caminho_projeto('.cache/reranker')
        pronto = (local / 'revision.txt').exists() and (local / 'revision.txt').read_text(encoding='utf8').strip() == config['revisao']
        if not pronto:
            raise ValueError('Prepare o reranker com python scripts/preparar_modelos.py')
        origem = str(local)
        kwargs = {'revision': config['revisao'], 'trust_remote_code': False}
        self.tokenizer = AutoTokenizer.from_pretrained(origem, **kwargs)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(
            origem, use_safetensors=True, **kwargs).eval().to('cpu')
        torch.set_num_threads(4)

    def ordenar(self, pergunta, candidatos):
        import torch
        notas = []
        for inicio in range(0, len(candidatos), self.config['lote']):
            lote = candidatos[inicio:inicio + self.config['lote']]
            # Preservar a pergunta; somente o documento pode ser truncado no par.
            entrada = self.tokenizer([pergunta] * len(lote), [c['texto'] for c in lote],
                padding=True, truncation='only_second', max_length=self.config['max_tokens'],
                return_tensors='pt')
            with torch.inference_mode():
                notas.extend(self.modelo(**entrada).logits.reshape(-1).cpu().tolist())
        if len(notas) != len(candidatos) or not np.isfinite(notas).all():
            raise ValueError('Reranker retornou pontuações inválidas')
        ordenados = [dict(c, score_reranker=float(n), posicao_rrf=i)
                     for i, (c, n) in enumerate(zip(candidatos, notas), 1)]
        neural = sorted(ordenados, key=lambda c: (-c['score_reranker'], c['posicao_rrf']))
        # Fusão por posição evita somar logits e notas RRF de escalas incompatíveis.
        for posicao, trecho in enumerate(neural, 1):
            trecho['posicao_neural'] = posicao
            k = self.config['rrf_k']
            trecho['score_final'] = 1 / (k + posicao) + 1 / (k + trecho['posicao_rrf'])
        return sorted(neural, key=lambda c: (-c['score_final'], c['posicao_rrf']))


@lru_cache(maxsize=1)
def _carregar(config_json):
    import json
    return Reranker(json.loads(config_json))


def reordenar(pergunta, candidatos, config):
    import json
    modelo = _carregar(json.dumps(config, sort_keys=True))
    return modelo.ordenar(pergunta, candidatos[:config['candidatos']])
