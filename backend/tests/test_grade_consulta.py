"""Consulta da grade: orquestração e rota HTTP com leitor e gerador falsos; sem rede nem arquivos do aluno."""
import json
import threading

import pytest
from fastapi.testclient import TestClient

import rag.grade_consulta as consulta
from rag.api import create_app
from rag.config import caminho_projeto
from rag.consulta.geracao import FalhaGeracao, resolver_resposta
from rag.grade_consulta import consultar_grade, montar_trechos
from rag.grade_visual import LeitorVisual, _LinhaTurma, _Leitura, montar_grade

MARCADOR = b'CONTEUDO-PRIVADO-DO-ARQUIVO'
PDF_FALSO = b'%PDF-1.4 ' + MARCADOR


def grade_exemplo():
    turmas = [('FGA0083', 'FCTE - I2'), ('FGA0244', 'FCTE - S10 / MOCAP'), ('FGA0210', 'A definir')]
    leitura = _Leitura(semestre='2025.1', turmas=[
        _LinhaTurma(codigo=c, nome=f'COMPONENTE {c}', carga_horaria=60, turma='Turma 01', local=l,
                    situacao='AGUARDANDO PROCESSAMENTO') for c, l in turmas])
    return montar_grade(leitura, 'pdf_visual', tabela_turmas=True, tabela_grade=False, periodo_visivel=True)


class LeitorFalso:
    def ler(self, conteudo):
        assert conteudo == PDF_FALSO
        return grade_exemplo()


class GeradorFalso:
    def __init__(self, falhar=False):
        self.chamadas, self.falhar = [], falhar

    def gerar(self, pergunta, trechos, contexto=None):
        self.chamadas.append({'pergunta': pergunta, 'trechos': trechos})
        if self.falhar:
            raise FalhaGeracao('Gemini fora do ar', 503)
        ids = [t['chunk_id'] for t in trechos if t['chunk_id'] in ('doc_FGA0083', 'base_FGA0083_0')]
        return resolver_resposta({'status': 'answered', 'message': '', 'claims': [
            {'text': 'A turma de FGA0083 tem situação aguardando processamento e fica no térreo da UAC.',
             'chunk_ids': ids}]}, trechos)


def test_resposta_separa_comprovante_e_base_e_nao_envia_o_arquivo():
    gerador = GeradorFalso()
    resposta = consultar_grade(PDF_FALSO, 'Onde fica a sala da FGA0083?', LeitorFalso(), gerador)
    assert resposta.respostaStatus == 'respondida' and resposta.resposta
    assert {c.origem for c in resposta.citacoes} == {'comprovante', 'base'}
    comprovante = next(c for c in resposta.citacoes if c.origem == 'comprovante')
    base = next(c for c in resposta.citacoes if c.origem == 'base')
    assert comprovante.referencia == 'FGA0083' and 'AGUARDANDO PROCESSAMENTO' in comprovante.trecho
    assert base.referencia == 'MAP-UAC-0' and 'Térreo' in base.trecho
    assert [f.identificador for f in resposta.fontes] == ['MAP-UAC-0']
    enviado = json.dumps(gerador.chamadas[0]['trechos'], ensure_ascii=False)
    assert MARCADOR.decode() not in enviado  # só fatos estruturados chegam ao gerador


def test_trechos_do_gerador_trazem_so_fatos_estruturados():
    trechos = {t['chunk_id']: t for t in montar_trechos(consulta.enriquecer_grade(grade_exemplo()))}
    assert 'Local declarado no comprovante: FCTE - I2' in trechos['doc_FGA0083']['texto']
    assert 'prédio UED; o andar não é confirmado' in trechos['base_FGA0244_1']['texto']
    assert 'A definir' in trechos['doc_FGA0210']['texto']
    assert trechos['doc_FGA0083']['source_id'] == 'COMPROVANTE'


def test_falha_no_vinculo_preserva_a_grade_e_marca_o_local_como_pendente(monkeypatch):
    def quebrar(grade, inventario=None):
        raise ValueError('inventário indisponível')
    monkeypatch.setattr(consulta, 'enriquecer_grade', quebrar)
    resposta = consultar_grade(PDF_FALSO, None, LeitorFalso(), GeradorFalso())
    assert [t.codigoComponente for t in resposta.grade.turmas] == ['FGA0083', 'FGA0244', 'FGA0210']
    pendentes = {t.codigoComponente for t in resposta.grade.turmas
                 if 'enriquecimento_indisponivel' in [p.codigo for p in t.pendencias]}
    assert pendentes == {'FGA0083', 'FGA0244'}  # "A definir" não tem local a vincular
    assert all(t.localizacoes == [] for t in resposta.grade.turmas)


def test_sem_pergunta_nao_chama_o_gerador():
    gerador = GeradorFalso()
    resposta = consultar_grade(PDF_FALSO, '  ', LeitorFalso(), gerador)
    assert resposta.respostaStatus == 'sem_pergunta' and resposta.resposta is None and gerador.chamadas == []
    assert len(resposta.grade.turmas) == 3


def test_falha_do_gerador_devolve_a_grade_sem_resposta():
    resposta = consultar_grade(PDF_FALSO, 'Pergunta?', LeitorFalso(), GeradorFalso(falhar=True))
    assert resposta.respostaStatus == 'indisponivel' and resposta.resposta is None and resposta.grade.turmas


def test_arquivo_sem_turmas_nao_chama_o_gerador():
    class Vazio:
        def ler(self, conteudo):
            return montar_grade(_Leitura(), 'imagem', tabela_turmas=False, tabela_grade=False, periodo_visivel=False)
    gerador = GeradorFalso()
    resposta = consultar_grade(b'x', 'Pergunta?', Vazio(), gerador)
    assert resposta.respostaStatus == 'insuficiente' and gerador.chamadas == []
    assert 'tabela_ausente' in [p.codigo for p in resposta.grade.pendencias]


# --- HTTP ---

class ServicoExemplo:
    info = {'status': 'ready', 'generationConfigured': True, 'sources': 1, 'chunks': 1, 'model': 'exemplo'}

    def close(self):
        pass


def cliente(grade):
    return TestClient(create_app(ServicoExemplo, grade=grade), base_url='http://localhost:8001')


def enviar(c, conteudo=PDF_FALSO, nome='comprovante.pdf', pergunta=None):
    return c.post('/api/v1/grade/consultar', files={'arquivo': (nome, conteudo, 'application/pdf')},
                  data={'pergunta': pergunta} if pergunta else {})


def pasta_execucoes():
    pasta = caminho_projeto('data/execucoes')
    return sorted(p.name for p in pasta.iterdir()) if pasta.exists() else []


def test_rota_devolve_grade_resposta_e_evidencias_sem_gravar_o_documento():
    antes = pasta_execucoes()
    gerador = GeradorFalso()
    with cliente(lambda c, p: consultar_grade(c, p, LeitorFalso(), gerador)) as c:
        r = enviar(c, pergunta='Onde fica a sala da FGA0083?')
    assert r.status_code == 200 and r.headers['cache-control'] == 'no-store'
    corpo = r.json()
    assert corpo['respostaStatus'] == 'respondida' and len(corpo['grade']['turmas']) == 3
    assert {c['origem'] for c in corpo['citacoes']} == {'comprovante', 'base'}
    assert pasta_execucoes() == antes  # nada gravado em data/execucoes


def test_rota_valida_tipo_no_servidor():
    leitor = LeitorVisual({'modelo': 'gemini-exemplo', 'timeout_s': 5}, 'chave-falsa')
    with cliente(lambda c, p: consultar_grade(c, p, leitor, GeradorFalso())) as c:
        r = enviar(c, b'isto nao e imagem nem pdf', nome='comprovante.pdf')
    assert r.status_code == 415  # o nome .pdf não basta: vale o conteúdo


def test_rota_recusa_arquivo_grande_vazio_e_ausente():
    with cliente(lambda c, p: consultar_grade(c, p, LeitorFalso(), GeradorFalso())) as c:
        assert enviar(c, b'0' * (9 * 1024 * 1024)).status_code == 413
        assert enviar(c, b'').status_code == 422
        assert c.post('/api/v1/grade/consultar', data={'pergunta': 'x'}).status_code == 422


def test_rota_so_aceita_uma_leitura_por_vez():
    liberar, iniciou = threading.Event(), threading.Event()

    def lenta(conteudo, pergunta):
        iniciou.set()
        liberar.wait(5)
        return consultar_grade(conteudo, pergunta, LeitorFalso(), GeradorFalso())
    with cliente(lenta) as c:
        primeira = {}
        t = threading.Thread(target=lambda: primeira.setdefault('r', enviar(c)))
        t.start()
        assert iniciou.wait(5)
        assert enviar(c).status_code == 429
        liberar.set()
        t.join(5)
        assert primeira['r'].status_code == 200
        assert enviar(c).status_code == 200  # a vaga foi liberada


def test_rota_indisponivel_sem_servico_de_leitura():
    with TestClient(create_app(ServicoExemplo), base_url='http://localhost:8001') as c:
        assert enviar(c).status_code == 503
