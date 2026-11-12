"""Persistência real do Chroma em tmp_path; vetores de exemplo, sem modelo/rede."""
import numpy as np
import pytest

from rag.armazenamento.indice import IndiceChroma
from rag.armazenamento.manifesto import contrato_embeddings, validar_contrato


def chunk(cid, sid='EX-001', validade='desconhecida'):
    return {'chunk_id': cid, 'source_id': sid, 'versao': 'exemplo-v1', 'texto': 'Texto de exemplo ' + cid,
            'titulo': 'Documento de exemplo', 'url': 'https://exemplo.invalid', 'secoes': ['Exemplo'],
            'campus': 'Gama', 'abrangencia': 'Gama', 'status': 'aprovado', 'rascunho': False,
            'data_revisao': '2026-11-11', 'revisor': 'Revisor de exemplo', 'validade': validade,
            'sha256_original': 'a' * 64, 'config_chunking': 'exemplo', 'tokens': 12, 'entidades': []}


def test_upsert_repetido_nao_duplica_e_indice_reabre(tmp_path):
    indice = IndiceChroma(tmp_path, 'exemplo', criar=True)
    chunks = [chunk('c_a'), chunk('c_b', 'EX-002')]
    vetores = np.array([[1., 0., 0.], [0., 1., 0.]], dtype=np.float32)
    indice.atualizar(chunks, vetores, lote=2)
    indice.atualizar(chunks, vetores, lote=2)
    reaberto = IndiceChroma(tmp_path, 'exemplo')
    assert reaberto.contar() == 2
    resultados = reaberto.consultar([1., 0., 0.], limite=2, data='2026-11-11')
    assert resultados[0]['chunk_id'] == 'c_a'
    assert resultados[0]['distancia'] == pytest.approx(0, abs=1e-6)
    assert resultados[0]['secoes'] == ['Exemplo']


def test_consulta_nao_retorna_validade_vencida(tmp_path):
    indice = IndiceChroma(tmp_path, 'exemplo', criar=True)
    indice.atualizar([chunk('c_a', validade='2000-01-01'), chunk('c_b', 'EX-002')],
                     np.array([[1., 0., 0.], [0., 1., 0.]]), lote=2)
    assert [c['chunk_id'] for c in indice.consultar([1., 0., 0.], 2, '2026-11-11')] == ['c_b']


def test_rascunho_nao_pode_ser_indexado(tmp_path):
    indice = IndiceChroma(tmp_path, 'exemplo', criar=True)
    with pytest.raises(ValueError, match='rascunho|aprovado'):
        indice.atualizar([dict(chunk('c_a'), rascunho=True)], np.array([[1., 0., 0.]]), lote=1)
    assert indice.contar() == 0


def test_mudanca_de_modelo_ou_prefixo_exige_novo_indice():
    cfg = {'modelo': 'exemplo', 'revisao': 'v1', 'dimensao': 3, 'max_tokens': 512,
           'prefixo_documento': 'passage: ', 'prefixo_pergunta': 'query: ', 'normalizar': True}
    contrato = contrato_embeddings(cfg)
    validar_contrato({'embeddings': contrato}, cfg)
    with pytest.raises(ValueError, match='incompat'):
        validar_contrato({'embeddings': contrato}, dict(cfg, revisao='v2'))
