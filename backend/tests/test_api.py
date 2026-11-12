"""API com serviço falso, sem E5, sem índice real e sem chamadas externas."""
from fastapi.testclient import TestClient
from rag.api import create_app
from rag.consulta.geracao import FalhaGeracao


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
