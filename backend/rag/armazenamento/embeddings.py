"""Embeddings E5 com prefixos explícitos e sem truncamento silencioso."""
import numpy as np


def validar_vetores(vetores, quantidade: int, dimensao: int, normalizados=True):
    matriz = np.asarray(vetores, dtype=np.float32)
    if matriz.shape != (quantidade, dimensao):
        raise ValueError(f'Dimensões incompatíveis: {matriz.shape}, esperado {(quantidade, dimensao)}')
    if not np.isfinite(matriz).all():
        raise ValueError('Embedding precisa conter somente números finitos')
    normas = np.linalg.norm(matriz, axis=1)
    if (normas == 0).any() or (normalizados and not np.allclose(normas, 1, atol=1e-3)):
        raise ValueError('Embedding nulo ou sem a normalização declarada')
    return matriz


class VetorizadorE5:
    def __init__(self, config: dict, modelo=None):
        self.config = config
        if modelo is None:
            from rag.config import configurar_cache
            configurar_cache({'embeddings': config})
            import torch
            from sentence_transformers import SentenceTransformer
            torch.set_num_threads(config.get('threads_cpu', 4))
            modelo = SentenceTransformer(
                config['modelo'], revision=config['revisao'],
                device=config.get('dispositivo', 'cpu'), trust_remote_code=False,
                model_kwargs={'use_safetensors': True},
            )
        self.modelo = modelo
        if modelo.get_sentence_embedding_dimension() != config['dimensao']:
            raise ValueError('Dimensão do modelo incompatível com a configuração')
        if config['max_tokens'] > modelo.max_seq_length:
            raise ValueError('Limite configurado ultrapassa a entrada do modelo')

    def _codificar(self, textos: list[str], prefixo: str, progresso=False):
        if not textos or any(not isinstance(t, str) or not t.strip() for t in textos):
            raise ValueError('Entrada vazia para embeddings')
        entradas = [prefixo + texto for texto in textos]
        # Contar antes do encode, que poderia truncar internamente.
        tokens = self.modelo.tokenizer(entradas, add_special_tokens=True, truncation=False,
                                      padding=False, return_attention_mask=False)['input_ids']
        for posicao, ids in enumerate(tokens):
            if len(ids) > self.config['max_tokens']:
                raise ValueError(f'Entrada {posicao}: {len(ids)} tokens; máximo {self.config["max_tokens"]}')
        vetores = self.modelo.encode(
            entradas, batch_size=self.config.get('lote', 16), prompt='',
            normalize_embeddings=self.config['normalizar'], convert_to_numpy=True,
            show_progress_bar=progresso,
        )
        return validar_vetores(vetores, len(entradas), self.config['dimensao'], self.config['normalizar'])

    def documentos(self, textos: list[str], progresso=False):
        return self._codificar(textos, self.config['prefixo_documento'], progresso)

    def pergunta(self, texto: str):
        return self._codificar([texto], self.config['prefixo_pergunta'])[0]
