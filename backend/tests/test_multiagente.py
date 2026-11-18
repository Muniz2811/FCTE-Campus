"""Testes sem rede, chave real, indice vetorial ou cota Gemini.

Rodar na raiz: .\\backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_multiagente.py -q
"""
from __future__ import annotations

import json
import threading
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace

import pytest

from rag.consulta.geracao import FalhaGeracao, SaidaGerador
from rag.consulta.multiagente import Limites, OrquestradorMultiagente, Parecer, Plano


TRECHO = {
    'chunk_id': 'c_cosmos', 'source_id': 'DOC-005', 'titulo': 'Laboratorios',
    'texto': 'COSMOS: Predio LDTEA, 2 andar, sala 304.',
    'url': 'https://example.org/campus/laboratorios', 'secoes':['Laboratorios'],
    'versao': '2026', 'data_revisao':'2026-11-01', 'validade':'desconhecida'
}


@pytest.fixture
def svc(monkeypatch,tmp_path):
    from rag.consulta import multiagente
    monkeypatch.setattr(multiagente, 'caminho_projeto', lambda value: tmp_path)
    return SimpleNamespace(
        config={'geracao':{'modelo':'gemini-test','temperatura':.1,'timeout_s':10,'max_output_tokens':512},
                'caminhos':{'execucoes':'data/execucoes'}},
        gerador=SimpleNamespace(chave='fake-key'),
        info={'baseVersion':'base-1','model':'gemini-test'},
        vaga=threading.BoundedSemaphore(1), entidades=None, modelo=None, base_lexical=None)


def plano(*_):
    return Plano(subconsultas=['Onde fica COSMOS?'],reformulacao='COSMOS LDTEA'), {'totalTokenCount':7}


def buscar(_):
    return {'assinatura_indice':'base-1','trechos':[TRECHO], 'candidatos_avaliados':[TRECHO]}


def saida(correta=True):
    return SaidaGerador.model_validate({'status':'answered','message':'',
        'claims':[{'text':'COSMOS fica no LDTEA, segundo andar, sala 304.' if correta else 'COSMOS fica na sala 101.',
                   'chunk_ids':['c_cosmos']} ]})


def test_aprovacao_e_rastreio(svc,tmp_path):
    def invocar(agent,*args):
        if agent=='pesquisador': return plano()
        if agent=='redator': return saida(), {'totalTokenCount':50,'promptTokenCount':30}
        return Parecer(decisao='aprovar',feedback='',claims_problematicas=[]), {'totalTokenCount':11}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert res['status']=='answered'
    assert res['llmCalls']==3
    assert res['usage']['totalTokenCount']==68
    assert res['claims'][0]['sourceIds']==['c_cosmos']
    assert [s['agent'] for s in res['trace']] == ['pesquisador','pesquisador','pesquisador','redator','revisor']
    log=json.loads((tmp_path/f'multiagent-{res["requestId"]}.json').read_text())
    assert log['baseVersion']=='base-1'
    assert log['decisaoFinal']=='aprovado'


def test_revisor_solicita_uma_correcao(svc):
    contador={'redator':0,'revisor':0}
    recebido=[]
    def invocar(agent,_prompt,_modelo,dados,_timeout):
        if agent=='pesquisador': return plano()
        if agent=='redator':
            contador['redator']+=1
            recebido.append((dados['feedback_revisor'],dados['claims_problematicas']))
            return saida(contador['redator']==2), {'totalTokenCount':10}
        contador['revisor']+=1
        decisao='corrigir' if contador['revisor']==1 else 'aprovar'
        return Parecer(decisao=decisao,feedback='A sala correta e a 304.' if decisao=='corrigir' else '', claims_problematicas=[0] if decisao=='corrigir' else []), {'totalTokenCount':7}
    result=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert result['status']=='answered'
    assert result['llmCalls']==5
    assert result['correctionRounds']==1
    assert contador=={'redator':2,'revisor':2}
    assert recebido==[('',[]),('A sala correta e a 304.',[0])]
    assert 'sala 304' in result['answer']
    assert any(s.get('decision')=='corrigir' for s in result['trace'])


def test_sem_evidencia_abstem_sem_redator(svc):
    def invocar(agent,*_):
        assert agent=='pesquisador'
        return plano()
    vazio=lambda _: {'assinatura_indice':'base-1','trechos':[]}
    result=OrquestradorMultiagente(svc,pesquisar=vazio,invocar=invocar).executar('A sala esta livre agora?')
    assert result['status']=='insufficient'
    assert result['llmCalls']==1
    assert result['correctionRounds']==0
    assert any(s['status']=='skipped' for s in result['trace'])


def test_citacao_nao_recuperada_e_bloqueada(svc,tmp_path):
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        return SaidaGerador.model_validate({'status':'answered','message':'',
            'claims':[{'text':'Local imaginario','chunk_ids':['id-inventado']}]}), {}
    with pytest.raises(FalhaGeracao):
        OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert svc.vaga.acquire(blocking=False), 'Trava deve ser liberada apos falha'
    svc.vaga.release()
    assert list(tmp_path.glob('multiagent-*.json')), 'Erro tambem deve deixar registro'


def test_limite_de_chamadas_e_respeitado(svc):
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator': return saida(False), {}
        return Parecer(decisao='corrigir',feedback='Corrija a sala',claims_problematicas=[0]), {}
    with pytest.raises(FalhaGeracao) as ex:
        OrquestradorMultiagente(svc,Limites(chamadas=3),pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert ex.value.status==429


def test_pergunta_composta_reune_evidencias_das_duas_buscas(svc):
    segundo={**TRECHO,'chunk_id':'c_lema','texto':'LEMA: LDTEA, terreo, sala 103.'}
    def pesquisa(query):
        return {'assinatura_indice':'base-1','trechos':[TRECHO if 'COSMOS' in query else segundo]}
    def invocar(agent,_prompt,_modelo,dados,_timeout):
        if agent=='pesquisador':
            return Plano(subconsultas=['Onde fica COSMOS?', 'Onde fica LEMA?'],reformulacao=''), {}
        if agent=='redator':
            ids={t['chunk_id'] for t in dados['evidencias']}
            assert ids=={'c_cosmos','c_lema'}
            return SaidaGerador.model_validate({'status':'answered','message':'',
                'claims':[{'text':'COSMOS no LDTEA, 2 andar, sala 304','chunk_ids':['c_cosmos']},
                          {'text':'LEMA no LDTEA, terreo, sala 103','chunk_ids':['c_lema']}]}), {}
        return Parecer(decisao='aprovar',feedback='',claims_problematicas=[]), {}
    res=OrquestradorMultiagente(svc,pesquisar=pesquisa,invocar=invocar).executar('Onde estao COSMOS e LEMA?')
    assert res['status']=='answered'
    assert len(res['retrieved'])==2
    assert len(res['searches'])==2
    assert {c['sourceIds'][0] for c in res['claims']}=={'c_cosmos','c_lema'}


def test_premissa_incorreta_deve_ser_corrigida(svc):
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator':
            return SaidaGerador.model_validate({'status':'answered','message':'',
                'claims':[{'text':'Nao. COSMOS fica no LDTEA, 2 andar, sala 304, nao na sala 101.',
                           'chunk_ids':['c_cosmos']}]}), {}
        return Parecer(decisao='aprovar',feedback='',claims_problematicas=[]), {}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('COSMOS fica na sala 101, correto?')
    assert res['status']=='answered'
    assert 'Nao.' in res['answer']


def test_revisor_declara_insuficiencia_mesmo_com_trechos(svc):
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator': return saida(), {}
        return Parecer(decisao='insuficiente',feedback='Trechos nao confirmam ocupacao ao vivo.',claims_problematicas=[]), {}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('A sala COSMOS esta livre agora?')
    assert res['status']=='insufficient'
    assert not res['claims']
    assert res['decision']=='insuficiente'


def test_abstencao_do_redator_preserva_mensagem_propria(svc):
    lacuna='A base cita o LDTEA, mas nao informa horario de funcionamento do COSMOS.'
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator':
            return SaidaGerador.model_validate({'status':'insufficient','message':lacuna,'claims':[]}), {}
        return Parecer(decisao='aprovar',feedback='',claims_problematicas=[]), {}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Qual o horario do COSMOS?')
    assert res['status']=='insufficient'
    assert res['message']==lacuna
    assert res['decision']=='insuficiente'


def test_recusa_apos_unica_correcao_e_identificada(svc):
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator': return saida(False), {}
        return Parecer(decisao='corrigir',feedback='Sala sem suporte.',claims_problematicas=[0]), {}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert res['status']=='insufficient' and not res['claims']
    assert res['decision']=='nao_aprovado_apos_correcao'
    assert res['correctionRounds']==1 and len(res['drafts'])==2


def test_falha_antes_do_fluxo_libera_trava(svc):
    svc.info={'model':'gemini-test'}  # sem baseVersion: KeyError ao montar o log
    with pytest.raises(FalhaGeracao) as ex:
        OrquestradorMultiagente(svc,pesquisar=buscar,invocar=lambda *_: plano()).executar('Onde fica COSMOS?')
    assert ex.value.status==503
    assert svc.vaga.acquire(blocking=False), 'Trava deve ser liberada'
    svc.vaga.release()


def test_falha_ao_gravar_log_nao_derruba_resposta(svc,monkeypatch):
    from rag.consulta import multiagente
    def disco_cheio(*_): raise OSError('disco cheio')
    monkeypatch.setattr(multiagente,'gravar_json',disco_cheio)
    def invocar(agent,*_):
        if agent=='pesquisador': return plano()
        if agent=='redator': return saida(), {}
        return Parecer(decisao='aprovar',feedback='',claims_problematicas=[]), {}
    res=OrquestradorMultiagente(svc,pesquisar=buscar,invocar=invocar).executar('Onde fica COSMOS?')
    assert res['status']=='answered'
    assert res['auditLogSaved'] is False
    assert svc.vaga.acquire(blocking=False)
    svc.vaga.release()
