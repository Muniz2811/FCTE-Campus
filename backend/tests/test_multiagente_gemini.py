"""Integracao REAL: indice local + Gemini. Gasta cota; pulado por padrao.

Rodar na raiz (cerca de 25 chamadas ao modelo configurado):
  $env:RAG_TEST_GEMINI='1'; .\\backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_multiagente_gemini.py -v -s

Cada execucao grava pergunta, resposta, trace, buscas, rascunhos e consumo em
avaliacao/resultados/multiagente-gemini-<UTC>/execucoes.json como evidencia das
issues #1 e #2. Asserts verificam fatos do gabarito de conferencia_final.json;
uma falha aqui e um achado de qualidade a registrar, nao algo para "repetir ate passar".
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import dotenv_values

from rag.armazenamento.manifesto import gravar_json
from rag.config import caminho_projeto, carregar_config, configurar_cache
from rag.consulta.geracao import FalhaGeracao, SaidaGerador
from rag.consulta.multiagente import (OrquestradorMultiagente, Parecer, Plano,
                                      PROMPT_PESQUISADOR, PROMPT_REDATOR, PROMPT_REVISOR)

ROOT = Path(__file__).resolve().parents[1]
ENV = dotenv_values(ROOT / '.env') if (ROOT / '.env').is_file() else {}
CHAVE = os.environ.get('GEMINI_API_KEY') or ENV.get('GEMINI_API_KEY') or ''
INTERVALO = float(os.environ.get('RAG_TEST_GEMINI_INTERVALO', '8'))

pytestmark = [
    pytest.mark.gemini,
    pytest.mark.skipif(os.environ.get('RAG_TEST_GEMINI') != '1' or not CHAVE,
                       reason='Defina RAG_TEST_GEMINI=1 e GEMINI_API_KEY para gastar cota real'),
]

CONFERENCIA = {q['id']: q for q in json.loads(
    (ROOT / 'avaliacao' / 'conferencia_final.json').read_text(encoding='utf-8'))['perguntas']}
EVIDENCIAS: list[dict] = []
FALHAS_PROVEDOR: list[dict] = []


def _sha(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


@pytest.fixture(scope='module')
def servico():
    from rag.consulta.servico import ServicoRAG
    cfg = carregar_config()
    cfg['geracao']['modelo'] = os.environ.get('GEMINI_MODEL') or ENV.get('GEMINI_MODEL') or cfg['geracao']['modelo']
    configurar_cache(cfg)
    svc = ServicoRAG(cfg, CHAVE)
    pasta = ROOT / 'avaliacao' / 'resultados' / ('multiagente-gemini-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    yield svc
    svc.close()
    if EVIDENCIAS:
        pasta.mkdir(parents=True, exist_ok=True)
        try:
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            commit = None
        gravar_json(pasta / 'execucoes.json', {
            'natureza': 'Testes de integracao com Gemini real (issues #1 e #2). Nao substitui a avaliacao da issue #4.',
            'gitHead': commit, 'modelo': cfg['geracao']['modelo'], 'geracao': cfg['geracao'],
            'baseVersion': svc.info['baseVersion'], 'retrievalSignature': svc.info.get('retrievalSignature'),
            'promptSha256': {'pesquisador': _sha(PROMPT_PESQUISADOR), 'redator': _sha(PROMPT_REDATOR),
                             'revisor': _sha(PROMPT_REVISOR)},
            'falhasProvedorRepetidas': FALHAS_PROVEDOR, 'casos': EVIDENCIAS})
        print(f'\nEvidencias gravadas em {pasta}')


@pytest.fixture(autouse=True)
def respeitar_cota():
    # Plano gratuito tem limite por minuto: espaca os casos.
    time.sleep(INTERVALO)


def orquestrador(servico, *, redator_falso=None):
    """Orquestrador real. 429 (cota) e 503 (alta demanda do provedor) esperam e repetem
    UMA vez: nenhum dos dois consome tokens. Repeticoes ficam em EVIDENCIAS['falhasProvedor'].

    redator_falso: substitui somente a PRIMEIRA chamada do Redator, para provar o Revisor real.
    """
    orq = OrquestradorMultiagente(servico)
    estado = {'redator': 0}

    def invocar(etapa, prompt, modelo, entrada, timeout):
        if etapa == 'redator':
            estado['redator'] += 1
            if redator_falso is not None and estado['redator'] == 1:
                return redator_falso(entrada), {}
        try:
            return orq._gemini(etapa, prompt, modelo, entrada, timeout)
        except FalhaGeracao as erro:
            if erro.status not in (429, 503):
                raise
            FALHAS_PROVEDOR.append({'etapa': etapa, 'status': erro.status, 'mensagem': str(erro),
                                    'em': datetime.now(timezone.utc).isoformat()})
            time.sleep(35)
            return orq._gemini(etapa, prompt, modelo, entrada, timeout)

    orq.invocar = invocar
    return orq


def registrar(caso, pergunta, resposta, **extra):
    EVIDENCIAS.append({'caso': caso, 'pergunta': pergunta, 'resposta': resposta, **extra})
    print(f"\n[{caso}] status={resposta.get('status')} decisao={resposta.get('decision')} "
          f"chamadas={resposta.get('llmCalls')} correcoes={resposta.get('correctionRounds')} "
          f"tokens={resposta.get('usage', {}).get('totalTokenCount')}")
    print('  ', resposta.get('answer') or resposta.get('message'))


def texto(resposta):
    return (resposta.get('answer') or resposta.get('message') or '').lower()


def test_schemas_estruturados_aceitos_pelo_gemini(servico):
    """Mais barato primeiro: uma chamada por agente prova que o Gemini aceita os tres esquemas."""
    orq = orquestrador(servico)
    evidencia = [{'chunk_id': 'c_teste', 'source_id': 'DOC-TESTE', 'titulo': 'Teste',
                  'texto': 'A biblioteca do campus Gama fica na UAC.'}]
    plano = orq.invocar('pesquisador', PROMPT_PESQUISADOR, Plano,
                        {'pergunta': 'Onde fica a biblioteca?', 'contexto': None}, 60)
    rascunho = orq.invocar('redator', PROMPT_REDATOR, SaidaGerador,
                           {'pergunta': 'Onde fica a biblioteca?', 'contexto': None, 'evidencias': evidencia,
                            'feedback_revisor': '', 'claims_problematicas': []}, 60)
    parecer = orq.invocar('revisor', PROMPT_REVISOR, Parecer,
                          {'pergunta': 'Onde fica a biblioteca?', 'contexto': None, 'evidencias': evidencia,
                           'resposta': rascunho[0].model_dump()}, 60)
    assert isinstance(plano[0], Plano) and plano[0].subconsultas
    assert isinstance(rascunho[0], SaidaGerador)
    assert isinstance(parecer[0], Parecer)
    EVIDENCIAS.append({'caso': 'schemas', 'plano': plano[0].model_dump(), 'rascunho': rascunho[0].model_dump(),
                       'parecer': parecer[0].model_dump(), 'uso': [plano[1], rascunho[1], parecer[1]]})


def test_pergunta_composta_H01(servico):
    q = CONFERENCIA['H01']
    res = orquestrador(servico).executar(q['pergunta'])
    registrar('H01_composta', q['pergunta'], res, referencia=q['referencia'])
    assert res['status'] == 'answered', res.get('message')
    assert len(res['searches']) >= 2, 'Pesquisador deveria decompor COSMOS e LEMA'
    assert '304' in texto(res) and '103' in texto(res)
    ids = {t['id'] for t in res['retrieved']}
    assert all(set(c['sourceIds']) <= ids for c in res['claims'])


def test_premissa_incorreta_H05(servico):
    q = CONFERENCIA['H05']
    res = orquestrador(servico).executar(q['pergunta'])
    registrar('H05_premissa_incorreta', q['pergunta'], res, referencia=q['referencia'])
    assert res['status'] == 'answered', res.get('message')
    assert '304' in texto(res), 'Deveria corrigir a premissa com a sala real'


def test_sem_resposta_na_base_H07(servico):
    q = CONFERENCIA['H07']
    res = orquestrador(servico).executar(q['pergunta'])
    registrar('H07_sem_resposta', q['pergunta'], res, referencia=q['referencia'])
    assert res['status'] == 'insufficient'
    assert not res['claims']


def test_revisor_real_detecta_afirmacao_sem_suporte(servico):
    """Redator falso afirma sala 101 citando um chunk real; o Revisor (Gemini) precisa recusar."""
    pergunta = 'Em que predio, andar e sala fica o laboratorio COSMOS?'

    def redator_errado(entrada):
        alvo = next((e for e in entrada['evidencias'] if 'cosmos' in e['texto'].lower()), entrada['evidencias'][0])
        return SaidaGerador.model_validate({'status': 'answered', 'message': '', 'claims': [
            {'text': 'O laboratorio COSMOS fica na sala 101, no terreo da UAC.', 'chunk_ids': [alvo['chunk_id']]}]})

    res = orquestrador(servico, redator_falso=redator_errado).executar(pergunta)
    decisoes = [s['decision'] for s in res['trace'] if s.get('decision')]
    registrar('revisor_detecta_erro_injetado', pergunta, res, decisoesRevisor=decisoes,
              observacao='Primeiro rascunho injetado (sala 101). Revisor e correcao sao chamadas reais.')
    assert decisoes and decisoes[0] != 'aprovar', 'Revisor aprovou afirmacao sem suporte'
    if decisoes[0] == 'corrigir':
        assert res['correctionRounds'] == 1
        assert '101' not in texto(res) or res['status'] == 'insufficient'


def test_complemento_de_conversa_com_previous_request(servico):
    primeira = 'Onde fica a biblioteca do campus Gama?'
    r1 = orquestrador(servico).executar(primeira)
    registrar('contexto_turno_1', primeira, r1)
    assert r1['status'] == 'answered', r1.get('message')
    time.sleep(INTERVALO)
    segunda = 'E la posso estudar em grupo ou so individualmente?'
    r2 = orquestrador(servico).executar(segunda, previous_request_id=r1['requestId'])
    registrar('contexto_turno_2', segunda, r2, previousRequestId=r1['requestId'])
    assert r2['status'] == 'answered', r2.get('message')
    assert 'grupo' in texto(r2)
    log = json.loads((caminho_projeto(servico.config['caminhos']['execucoes']) /
                      f"multiagent-{r2['requestId']}.json").read_text(encoding='utf-8'))
    assert log['previousRequestId'] == r1['requestId']
