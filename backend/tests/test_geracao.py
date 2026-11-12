"""Citações e protocolo Gemini com HTTP falso; não usa chave real nem rede."""
import json
import httpx
import pytest

from rag.consulta.geracao import GeradorGemini, FalhaGeracao, resolver_resposta

TRECHOS = [{'chunk_id': 'c_exemplo', 'source_id': 'EX-001', 'titulo': 'Fonte de exemplo',
            'texto': 'A biblioteca tem mesas para estudo.', 'url': 'https://exemplo.invalid',
            'secoes': ['Biblioteca'], 'versao': 'exemplo-v1', 'data_revisao': '2026-11-11',
            'validade': 'desconhecida', 'distancia': .1}]
CONFIG = {'modelo': 'gemini-exemplo', 'temperatura': .1, 'timeout_s': 10, 'max_output_tokens': 100}


def test_resolve_citacoes_ate_trecho_fonte_e_versao():
    result = resolver_resposta({'status': 'answered', 'message': '', 'claims': [
        {'text': 'A biblioteca tem mesas para estudo.', 'chunk_ids': ['c_exemplo']}]}, TRECHOS)
    assert result['answer'] == 'A biblioteca tem mesas para estudo. [1]'
    assert result['sources'][0]['id'] == 'c_exemplo'
    assert result['sources'][0]['version'] == 'exemplo-v1'
    assert result['claims'][0]['sourceIds'] == ['c_exemplo']


@pytest.mark.parametrize('ids', [[], ['c_inventado']])
def test_rejeita_afirmacao_sem_evidencia_recuperada(ids):
    with pytest.raises(FalhaGeracao):
        resolver_resposta({'status': 'answered', 'message': '', 'claims': [{'text': 'Afirmacao.', 'chunk_ids': ids}]}, TRECHOS)


def test_ausencia_nao_fabrica_citacoes():
    result = resolver_resposta({'status': 'insufficient', 'claims': [], 'message': 'Não há informação de ocupação atual na base.'}, TRECHOS)
    assert result['status'] == 'insufficient'
    assert result['sources'] == []


def test_api_key_fica_no_cabecalho_e_nao_na_url_e_json_e_validado():
    def responder(request):
        assert request.headers['x-goog-api-key'] == 'chave-de-exemplo'
        assert 'chave-de-exemplo' not in str(request.url)
        payload = json.loads(request.content)
        assert payload['generationConfig']['responseMimeType'] == 'application/json'
        text = json.dumps({'status': 'insufficient', 'claims': [], 'message': 'Sem dados.'})
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': text}]}}]})
    gerador = GeradorGemini(CONFIG, 'chave-de-exemplo', transport=httpx.MockTransport(responder))
    assert gerador.gerar('Ocupação agora?', TRECHOS)['status'] == 'insufficient'
    gerador.close()


def test_quota_e_erro_seguro_sem_expor_resposta_do_provedor():
    gerador = GeradorGemini(CONFIG, 'chave-de-exemplo', transport=httpx.MockTransport(
        lambda _: httpx.Response(429, json={'error': {'message': 'conteudo externo'}})))
    with pytest.raises(FalhaGeracao) as exc:
        gerador.gerar('Pergunta', TRECHOS)
    assert exc.value.status == 429
    assert 'conteudo externo' not in str(exc.value)
    gerador.close()
