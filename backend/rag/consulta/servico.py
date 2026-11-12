"""Caso de uso do chat. Reutiliza o E5 e registra pergunta, evidências e resposta."""
import threading
from datetime import datetime, timezone
from uuid import uuid4

from rag.consulta.busca import buscar
from rag.config import caminho_projeto
from rag.armazenamento.embeddings import VetorizadorE5
from rag.consulta.geracao import GeradorGemini, FalhaGeracao, fonte_publica, PROMPT
from rag.armazenamento.indexacao import abrir_indice
from rag.armazenamento.manifesto import gravar_json, hash_bytes
from rag.consulta.conversa import contexto_da_consulta, consulta_contextualizada
from rag.ingestao.normalizacao import carregar_entidades, compilar


class ServicoRAG:
    def __init__(self, config, chave, modelo=None, gerador=None):
        self.config = config
        indice, manifesto = abrir_indice(config)
        self.info = {'status': 'ready', 'generationConfigured': bool(chave),
                     'sources': manifesto['corpus']['total_fontes'], 'chunks': indice.contar(),
                     'baseVersion': manifesto['assinatura'], 'model': config['geracao']['modelo']}
        self.modelo = modelo if modelo is not None else VetorizadorE5(config['embeddings'])
        self.entidades = compilar(carregar_entidades(caminho_projeto(config['caminhos']['entidades'])))
        self.gerador = gerador if gerador is not None else GeradorGemini(config['geracao'], chave)
        self.vaga = threading.BoundedSemaphore(1)

    def close(self):
        self.gerador.close()

    def perguntar(self, texto, place_id=None, previous_request_id=None):
        if not self.info['generationConfigured']:
            raise FalhaGeracao('Configure GEMINI_API_KEY no ambiente do backend RAG.', 503)
        if not self.vaga.acquire(blocking=False):
            raise FalhaGeracao('Já há uma consulta em andamento. Aguarde a resposta antes de enviar outra.', 429)
        request_id = str(uuid4())
        registro = {'requestId': request_id, 'executado_em': datetime.now(timezone.utc).isoformat(),
                    'pergunta': texto, 'placeId': place_id, 'geracao': self.config['geracao'],
                    'previousRequestId': previous_request_id,
                    'prompt': {'versao': 'campus-rag-v2', 'sha256': hash_bytes(PROMPT.encode('utf-8'))}}
        try:
            contexto = contexto_da_consulta(texto, previous_request_id,
                caminho_projeto(self.config['caminhos']['execucoes']), self.info['baseVersion'], self.entidades)
            consulta = consulta_contextualizada(texto, contexto)
            registro['contexto_conversa'] = contexto
            registro['consulta_busca'] = consulta
            recuperacao = buscar(consulta, self.config, modelo=self.modelo)
            registro['recuperacao'] = recuperacao
            resultado = self.gerador.gerar(texto, recuperacao['trechos'], contexto=contexto)
            resposta = {**resultado, 'requestId': request_id, 'baseVersion': recuperacao['assinatura_indice'],
                        'model': self.config['geracao']['modelo'],
                        'retrieved': [fonte_publica(t) for t in recuperacao['trechos']]}
            registro['resposta'] = resposta
            gravar_json(caminho_projeto(self.config['caminhos']['execucoes']) / f'chat-{request_id}.json', registro)
            return resposta
        except FalhaGeracao as erro:
            registro['erro'] = {'status': erro.status, 'message': str(erro)}
            gravar_json(caminho_projeto(self.config['caminhos']['execucoes']) / f'chat-{request_id}.json', registro)
            raise
        finally:
            self.vaga.release()
