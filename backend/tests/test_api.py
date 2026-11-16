"""API com serviço falso, sem E5, sem índice real e sem chamadas externas."""
from fastapi.testclient import TestClient
from rag.api import create_app
from rag.consulta.geracao import FalhaGeracao
from rag.acesso import Acesso
import pytest


class ServicoExemplo:
    info = {'status': 'ready', 'generationConfigured': True, 'sources': 1, 'chunks': 1, 'model': 'exemplo'}
    def perguntar(self, texto, place_id=None):
        return {'status': 'insufficient', 'message': 'Base de exemplo sem essa resposta.', 'sources': [], 'retrieved': []}
    def close(self):
        pass


def test_health_e_contrato_do_chat_sem_cache():
    with TestClient(create_app(ServicoExemplo), base_url='http://localhost:8001') as client:
        assert client.get('/api/v1/health').json()['sources'] == 1
        response = client.post('/api/v1/chat', json={'text': 'Onde fica a biblioteca?', 'campus': 'gama'})
        assert response.status_code == 200
        assert response.json()['status'] == 'insufficient'
        assert response.headers['cache-control'] == 'no-store'
        assert client.post('/api/v1/chat', json={'text': ' ', 'campus': 'gama'}).status_code == 422
        assert client.post('/api/v1/chat', json={'text': 'Pergunta', 'campus': 'outro'}).status_code == 422


def test_origem_estranha_nao_pode_disparar_consulta():
    with TestClient(create_app(ServicoExemplo), base_url='http://localhost:8001') as client:
        assert client.post('/api/v1/chat', json={'text': 'Pergunta'}, headers={'Origin': 'https://exemplo.invalid'}).status_code == 403
        assert client.post('/api/v1/chat', json={'text': 'Pergunta'}, headers={'Origin': 'http://127.0.0.1:5173'}).status_code == 200


def test_inicializacao_falha_expoe_indisponibilidade_sem_excecao_bruta():
    def falhar():
        raise ValueError('detalhe interno de exemplo')
    with TestClient(create_app(falhar), base_url='http://localhost:8001') as client:
        assert client.get('/api/v1/health').status_code == 503
        r = client.post('/api/v1/chat', json={'text': 'Pergunta'})
        assert r.status_code == 503
        assert 'detalhe interno' not in r.text


def test_quota_e_preservada_no_http_para_interface():
    class Ocupado(ServicoExemplo):
        def perguntar(self, *args):
            raise FalhaGeracao('Aguarde a consulta anterior.', 429)
    with TestClient(create_app(Ocupado), base_url='http://localhost:8001') as client:
        assert client.post('/api/v1/chat', json={'text': 'Pergunta'}).status_code == 429


def test_chat_online_publico_e_integracao_protegida_por_token(monkeypatch, tmp_path):
    (tmp_path / 'index.html').write_text('<html>Chat FCTE</html>', encoding='utf-8')
    monkeypatch.setenv('RAG_WEB_DIR', str(tmp_path))
    acesso = Acesso(True, 't' * 40)
    with TestClient(create_app(ServicoExemplo, acesso=acesso), base_url='https://localhost') as client:
        pagina = client.get('/')
        assert pagina.status_code == 200 and 'www-authenticate' not in pagina.headers
        assert client.get('/index.html').status_code == 200
        assert client.get('/api/v1/health').status_code == 200
        assert client.post('/api/v1/chat', json={'text': 'Onde fica?'}).status_code == 200
        for path in ('/api/v1/comparison/llm', '/api/v1/comparison/rag'):
            assert client.post(path, json={}).status_code == 422  # sem bloqueio de login
        assert client.post('/perguntar', json={'pergunta': 'Onde fica?'}).status_code == 401
        assert client.post('/perguntar', json={'pergunta': 'Onde fica?'}, auth=('equipe', 'legado')).status_code == 401
        assert client.post('/perguntar', json={'pergunta': 'Onde fica?'}, headers={'Authorization': 'Bearer errado'}).status_code == 401


def test_contrato_comum_preserva_fontes_versao_e_limite_sem_mudar_chat():
    class Federado(ServicoExemplo):
        config = {'busca': {'top_k': 5}}
        def perguntar(self, texto, place_id=None, previous_request_id=None, *, max_trechos=None):
            self.recebido = (texto, previous_request_id, max_trechos)
            fonte = {'id': 'chunk-1', 'sourceId': 'DOC-012', 'title': 'Biblioteca', 'excerpt': 'Há cabines individuais.',
                     'url': 'https://bce.unb.br/biblioteca-campus-gama/', 'version': '2026-11-11', 'section': 'Estudo'}
            return {'status': 'answered', 'answer': 'Há cabines individuais. [1]', 'sources': [fonte], 'retrieved': [fonte],
                    'claims': [{'text': 'Há cabines individuais.', 'sourceIds': ['chunk-1']}],
                    'requestId': '87d58dee-d3d0-4e6a-8b69-acbc3a223585', 'baseVersion': 'assinatura', 'model': 'exemplo'}
    servico = Federado()
    acesso = Acesso(True, 't' * 40)
    with TestClient(create_app(lambda: servico, acesso=acesso), base_url='https://localhost') as client:
        headers = {'Authorization': f'Bearer {acesso.token}'}
        r = client.post('/perguntar', json={'pergunta': 'Há cabines?', 'contexto': {'campus': 'gama', 'data': '2026-11-13'}, 'max_trechos': 2}, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert d['grupo'] == 'grupo09' and d['status'] == 'answered' and d['encontrou_base']
        assert d['fontes'][0]['chunk_id'] == 'chunk-1' and d['fontes'][0]['versao'] == '2026-11-11'
        assert d['afirmacoes'][0]['chunk_ids'] == ['chunk-1'] and d['base_version'] == 'assinatura'
        assert servico.recebido == ('Há cabines?', None, 2)
        r = client.post('/perguntar', json={'pergunta': 'Há cabines?', 'max_trechos': 20}, headers=headers)
        assert r.json()['max_trechos_aplicado'] == 5
        assert client.post('/perguntar', json={'pergunta': 'Onde?', 'contexto': {'campus': 'darcy'}}, headers=headers).status_code == 422


def test_falha_remota_tem_status_diferente_de_ausencia_e_sem_vazar_erro():
    with TestClient(create_app(lambda: (_ for _ in ()).throw(ValueError('privado'))), base_url='http://localhost') as client:
        r = client.post('/perguntar', json={'pergunta': 'Onde fica?'})
        assert r.status_code == 503 and r.json()['status'] == 'unavailable'
        assert not r.json()['encontrou_base'] and 'privado' not in r.text


def test_deploy_exige_token_e_tentativas_invalidas_tem_limite(monkeypatch):
    monkeypatch.setenv('RAG_ALLOWED_HOSTS', 'fcte.example.org')
    monkeypatch.setenv('RAG_REQUIRE_AUTH', 'false')
    with pytest.raises(ValueError, match='exige RAG_REQUIRE_AUTH'):
        Acesso.do_ambiente()
    monkeypatch.setenv('RAG_ALLOWED_HOSTS', 'localhost')
    acesso = Acesso(True, 't' * 40)
    with TestClient(create_app(ServicoExemplo, acesso=acesso), base_url='https://localhost') as client:
        for _ in range(10):
            assert client.post('/perguntar', json={'pergunta': 'Onde?'}, headers={'Authorization': 'Bearer errado'}).status_code == 401
        r = client.post('/perguntar', json={'pergunta': 'Onde?'}, headers={'Authorization': 'Bearer errado'})
        assert r.status_code == 429 and r.headers['retry-after'] == '60'
        assert client.get('/api/v1/health').status_code == 200
        assert client.post('/api/v1/chat', json={'text': 'Onde?'}).status_code == 200
