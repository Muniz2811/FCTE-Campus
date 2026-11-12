"""Contrato do embedder com modelo pequeno falso. Sem rede e sem download."""
import numpy as np
import pytest

from rag.armazenamento.embeddings import VetorizadorE5

CFG = {"modelo": "exemplo/falso", "revisao": "1", "dimensao": 3, "max_tokens": 8,
       "prefixo_documento": "passage: ", "prefixo_pergunta": "query: ", "normalizar": True,
       "dispositivo": "cpu", "lote": 2, "threads_cpu": 1}


class ModeloExemplo:
    max_seq_length = 8
    def __init__(self):
        self.entradas = []
    def get_sentence_embedding_dimension(self):
        return 3
    def tokenizer(self, textos, **kwargs):
        assert kwargs['truncation'] is False
        return {"input_ids": [list(range(len(t.split()) + 2)) for t in textos]}
    def encode(self, textos, **kwargs):
        self.entradas = textos
        assert kwargs['normalize_embeddings'] is True
        assert kwargs['prompt'] == ''
        return np.array([[1., 0., 0.]] * len(textos), dtype=np.float32)


def test_documentos_e_perguntas_usam_prefixos_distintos():
    modelo = ModeloExemplo()
    embedder = VetorizadorE5(CFG, modelo=modelo)
    assert embedder.documentos(['Biblioteca', 'UAC']).shape == (2, 3)
    assert modelo.entradas == ['passage: Biblioteca', 'passage: UAC']
    assert embedder.pergunta('Onde fica?').shape == (3,)
    assert modelo.entradas == ['query: Onde fica?']


def test_impede_truncamento_silencioso_e_pergunta_vazia():
    embedder = VetorizadorE5(CFG, modelo=ModeloExemplo())
    with pytest.raises(ValueError, match='tokens'):
        embedder.documentos(['palavra ' * 10])
    with pytest.raises(ValueError, match='vazia'):
        embedder.pergunta('  ')


def test_rejeita_vetor_invalido_antes_de_indexar():
    class ModeloInvalido(ModeloExemplo):
        def encode(self, textos, **kwargs):
            return np.array([[np.nan, 0., 0.]])
    with pytest.raises(ValueError, match='finito'):
        VetorizadorE5(CFG, modelo=ModeloInvalido()).documentos(['Texto'])
