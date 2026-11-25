"""Caso de uso do chat. Reutiliza o E5 e registra pergunta, evidências e resposta."""
import threading
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from rag.consulta.busca import buscar
from rag.config import caminho_projeto
from rag.consulta.geracao import GeradorGemini, FalhaGeracao, fonte_publica, PROMPT
from rag.armazenamento.leitura import abrir_indice, carregar_base_lexical
from rag.armazenamento.manifesto import gravar_json, hash_bytes, hash_json
from rag.consulta.conversa import contexto_da_consulta, consulta_contextualizada
from rag.ingestao.normalizacao import carregar_entidades, compilar


from rag.monitor import etapa


class ServicoRAG:
    def __init__(self, config, chave, modelo=None, gerador=None):
        self.config = config
        indice, manifesto = abrir_indice(config)
        lexical = config['busca']['metodo'] == 'bm25'
        self.info = {'status': 'ready', 'generationConfigured': bool(chave),
                     'sources': manifesto['corpus']['total_fontes'], 'chunks': indice.contar(),
                     'baseVersion': manifesto['assinatura'], 'model': config['geracao']['modelo'],
                     'vectorStore': config['indice'].get('backend', 'chroma'),
                     'retrievalProfile': config.get('perfil', 'full'),
                     'retrievalMethod': config['busca']['metodo'], 'vectorSearchEnabled': not lexical,
                     'rerankerEnabled': bool(config['busca'].get('reranker', {}).get('ativo')),
                     'retrievalSignature': hash_json(config['busca'])}
        self.base_lexical = carregar_base_lexical(indice, manifesto, config) if lexical else None
        self.modelo = modelo
        if not lexical and modelo is None:
            from rag.armazenamento.embeddings import VetorizadorE5
            self.modelo = VetorizadorE5(config['embeddings'])
        self.entidades = compilar(carregar_entidades(caminho_projeto(config['caminhos']['entidades'])))
        self.gerador = gerador if gerador is not None else GeradorGemini(config['geracao'], chave)
        self.vaga = threading.BoundedSemaphore(1)

    def close(self):
        self.gerador.close()

    def perguntar(self, texto, place_id=None, previous_request_id=None, *, max_trechos=None):
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
            config_busca = self.config
            if max_trechos is not None:
                config_busca = deepcopy(self.config)
                config_busca['busca']['top_k'] = min(max_trechos, self.config['busca']['top_k'])
            with etapa('Busca') as evento:
                recuperacao = buscar(consulta, config_busca, modelo=self.modelo, base_lexical=self.base_lexical)
                evento['trechos'] = len(recuperacao['trechos'])
                evento['detalhe'] = self.info['retrievalMethod']
            registro['recuperacao'] = recuperacao
            with etapa('Geração') as evento:
                evento['modelo'] = self.config['geracao']['modelo']
                resultado = self.gerador.gerar(texto, recuperacao['trechos'], contexto=contexto)
                evento['tokens'] = resultado.get('usage', {}).get('totalTokenCount')
            resposta = {**resultado, 'requestId': request_id, 'baseVersion': recuperacao['assinatura_indice'],
                        'model': self.config['geracao']['modelo'],
                        'retrievalProfile': self.info['retrievalProfile'],
                        'retrievalMethod': self.info['retrievalMethod'],
                        'retrievalSignature': self.info['retrievalSignature'],
                        'rerankerEnabled': self.info['rerankerEnabled'],
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
