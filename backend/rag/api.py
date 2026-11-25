"""Chat e API v1. Em produção, a mesma aplicação serve o build do frontend."""
import asyncio
import logging
import secrets
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from dotenv import dotenv_values
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from rag.config import carregar_config, caminho_projeto, configurar_cache, ambiente_backend
from rag.consulta.geracao import FalhaGeracao, GeradorGemini
from rag.consulta.servico import ServicoRAG
from rag.consulta.comparacao import Comparador, painel_historico
from rag.consulta.multiagente import OrquestradorMultiagente
from rag.acesso import Acesso
from rag import monitor
from rag.integracao import PerguntaIntegracao, RespostaIntegracao, resposta_integracao, indisponivel
from rag.consulta.locais import consultar_locais
from rag.grade import RespostaGrade
from rag.grade_consulta import consultar_grade
from rag.grade_visual import LeitorVisual, LIMITE_BYTES

ROTA_GRADE = '/api/v1/grade/consultar'
LIMITE_CORPO_GRADE = LIMITE_BYTES + 64 * 1024  # arquivo + campos do multipart
TIMEOUT_GERACAO_GRADE_S = 30


class Pergunta(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1200)
    campus: Literal['gama'] = 'gama'
    placeId: str | None = Field(default=None, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    previousRequestId: UUID | None = None


def criar_servico():
    config = carregar_config()
    configurar_cache(config)
    # Um caminho explicitamente fornecido pode reutilizar a chave existente, sem copiar .env.
    arquivo = Path(os.environ.get('RAG_ENV_FILE', caminho_projeto('.env')))
    valores = dotenv_values(arquivo) if arquivo.is_file() else {}
    chave = os.environ.get('GEMINI_API_KEY') or valores.get('GEMINI_API_KEY') or ''
    config['geracao']['modelo'] = os.environ.get('GEMINI_MODEL') or valores.get('GEMINI_MODEL') or config['geracao']['modelo']
    log = logging.getLogger('uvicorn.error')
    log.info('Inicializando RAG: perfil=%s, busca=%s, armazenamento=%s',
             config.get('perfil', 'full'), config['busca']['metodo'], config['indice']['backend'])
    servico = ServicoRAG(config, chave)
    log.info('RAG pronto: %s fontes, %s chunks, reranker=%s',
             servico.info['sources'], servico.info['chunks'], servico.info['rerankerEnabled'])
    return servico


def create_app(factory=criar_servico, *, acesso=None, grade=None):
    """`grade(conteudo, pergunta)` é injetável em testes; por padrão usa o leitor visual e o gerador do serviço."""
    acesso = acesso if acesso is not None else Acesso.do_ambiente()
    vaga_grade = threading.BoundedSemaphore(1)  # uma leitura de documento por vez: cota do Gemini e memória
    @asynccontextmanager
    async def lifespan(app):
        try:
            app.state.rag = await asyncio.to_thread(factory)
        except Exception as erro:
            logging.getLogger(__name__).error('Inicialização do RAG falhou: %s', type(erro).__name__)
            app.state.rag = None
        app.state.comparador = Comparador(app.state.rag) if app.state.rag is not None else None
        servico = app.state.rag
        if grade is not None:
            app.state.grade = grade
        elif servico is not None and hasattr(servico, 'gerador'):
            leitor = LeitorVisual(servico.config['geracao'], servico.gerador.chave)
            # Gerador próprio com timeout curto: uma chamada pendurada é repetida em vez de esperar 90 s.
            gerador = GeradorGemini({**servico.config['geracao'], 'timeout_s': TIMEOUT_GERACAO_GRADE_S}, servico.gerador.chave)
            app.state.grade = lambda conteudo, pergunta: consultar_grade(conteudo, pergunta, leitor, gerador)
        else:
            app.state.grade = None
        yield
        if app.state.rag is not None:
            app.state.rag.close()

    app = FastAPI(title='FCTE Campus · Assistente RAG', version='1.0.0', lifespan=lifespan,
                  docs_url=None if acesso.somente_integracao else '/docs',
                  redoc_url=None if acesso.somente_integracao else '/redoc',
                  openapi_url=None if acesso.somente_integracao else '/openapi.json')
    ambiente = ambiente_backend()
    hosts = [host.strip() for host in ambiente.get('RAG_ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',') if host.strip()]
    # O health check usa o domínio público real, que pode diferir do exemplo no .env.
    host_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
    if host_render and host_render not in hosts:
        hosts.append(host_render)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    origens = set(ambiente.get('RAG_ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173').split(','))

    leitura = ambiente.get('RAG_MONITOR_READ_TOKEN') or ''
    painel = '/api/v1/monitor'
    ingestao = painel + '/eventos'

    @app.middleware('http')
    async def proteger(request, call_next):
        if acesso.somente_integracao and request.url.path not in {'/perguntar', '/api/v1/health', '/api/v1/multiagent', painel, ingestao}:
            return JSONResponse({'detail': 'Not Found'}, status_code=404)
        origem = request.headers.get('origin')
        if origem and origem not in origens and origem != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Origem não autorizada.'}, status_code=403)
        if request.method == 'POST':
            try:
                limite = LIMITE_CORPO_GRADE if request.url.path == ROTA_GRADE else 8192
                if int(request.headers.get('content-length', '0')) > limite:
                    return JSONResponse({'detail': 'Arquivo muito grande.' if limite != 8192 else 'Pergunta muito grande.'}, status_code=413)
            except ValueError:
                return JSONResponse({'detail': 'Requisição inválida.'}, status_code=400)
        bloqueio = await acesso.proteger(request)
        if bloqueio is not None:
            return bloqueio
        caminho = request.url.path
        if caminho in {painel, ingestao}:
            chave = leitura if caminho == painel else acesso.token
            if len(chave) < 32 or not secrets.compare_digest(
                request.headers.get('authorization', '').encode(), ('Bearer ' + chave).encode()
            ):
                return JSONResponse({'detail': 'Credencial do monitor inválida.'}, status_code=401)
        instrumentar = caminho in {'/perguntar', '/api/v1/chat', '/api/v1/multiagent'} or caminho.startswith('/api/v1/comparison/')
        if instrumentar and request.method == 'POST':
            trace, parent = str(uuid4()), None
            if caminho == '/perguntar' and acesso.obrigatorio:
                try:
                    trace_recebido = UUID(request.headers.get('x-milton-trace', ''))
                    parent = str(UUID(request.headers.get('x-milton-parent', '')))
                    trace = str(trace_recebido)
                except ValueError:
                    pass
            token = monitor.contexto.set((trace, parent))
            try:
                with monitor.etapa('FCTE-Campus ' + caminho) as evento:
                    resposta = await call_next(request)
                    if resposta.status_code >= 400:
                        evento['resultado'] = 'erro'
                    evento['http'] = resposta.status_code
            finally:
                monitor.contexto.reset(token)
        else:
            resposta = await call_next(request)
        resposta.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') or request.url.path == '/perguntar' else 'no-cache'
        resposta.headers['X-Content-Type-Options'] = 'nosniff'
        return resposta

    @app.exception_handler(FalhaGeracao)
    async def falha_geracao(_request, erro):
        return JSONResponse({'detail': str(erro)}, status_code=erro.status)

    @app.post(ingestao, status_code=200)
    def receber_evento(evento: monitor.EventoMilton):
        monitor.registrar(evento.model_dump(mode='json'))

    @app.get(painel)
    def monitor_ao_vivo():
        return {'execucoes': monitor.recentes()}

    @app.get('/api/v1/health')
    def health():
        servico = app.state.rag
        if servico is None:
            return JSONResponse({'status': 'unavailable', 'message': 'Não foi possível abrir o RAG. Confira o índice e o terminal do backend.'}, status_code=503)
        return servico.info

    @app.post('/api/v1/chat')
    def chat(pergunta: Pergunta):
        if app.state.rag is None:
            raise FalhaGeracao('O RAG ainda não está disponível. Confira o terminal do backend.', 503)
        try:
            if pergunta.previousRequestId is not None:
                return app.state.rag.perguntar(pergunta.text, pergunta.placeId, str(pergunta.previousRequestId))
            return app.state.rag.perguntar(pergunta.text, pergunta.placeId)
        except ValueError:
            raise FalhaGeracao('A base está desatualizada ou a pergunta excede o limite de tokens. Confira o índice e reformule.', 503) from None
        except OSError:
            raise FalhaGeracao('Não foi possível acessar o índice ou salvar a execução local.', 503) from None

    @app.post('/perguntar', response_model=RespostaIntegracao,
              responses={401: {'description': 'Token Bearer ausente ou inválido'},
                         429: {'description': 'Serviço ocupado ou cota atingida'},
                         503: {'description': 'Serviço indisponível'}, 504: {'description': 'Timeout da geração'}})
    def perguntar_integracao(entrada: PerguntaIntegracao):
        inicio = time.monotonic()
        try:
            servico = app.state.rag
            if servico is None:
                raise FalhaGeracao('O RAG do Grupo 09 está indisponível.', 503)
            if entrada.contexto.navegacao is not None:
                resultado = consultar_locais(entrada.contexto.navegacao, servico.config, servico.info['baseVersion'])
                resultado['tempo_ms'] = int((time.monotonic() - inicio) * 1000)
                return resultado
            limite = min(entrada.max_trechos, servico.config['busca']['top_k'])
            anterior = entrada.contexto.previous_request_id
            resposta = servico.perguntar(entrada.pergunta, previous_request_id=str(anterior) if anterior else None,
                                        max_trechos=limite)
            return resposta_integracao(resposta, int((time.monotonic() - inicio) * 1000), limite)
        except (FalhaGeracao, ValueError, OSError) as erro:
            status = erro.status if isinstance(erro, FalhaGeracao) else 503
            mensagem = str(erro) if isinstance(erro, FalhaGeracao) else 'Não foi possível consultar a base do Grupo 09.'
            return JSONResponse(indisponivel(mensagem, status, int((time.monotonic() - inicio) * 1000)), status_code=status)

    @app.post(ROTA_GRADE, response_model=RespostaGrade,
              responses={413: {'description': 'Arquivo acima de 8 MB'}, 415: {'description': 'Tipo de arquivo não aceito'},
                         422: {'description': 'Arquivo ilegível'}, 429: {'description': 'Leitura em andamento ou cota atingida'},
                         503: {'description': 'Serviço indisponível'}})
    def grade_consultar(arquivo: UploadFile = File(...), pergunta: str | None = Form(default=None, max_length=1200)):
        # Rota pública como o chat. O arquivo é lido só em memória; nada é gravado em data/execucoes.
        if app.state.grade is None:
            raise FalhaGeracao('A leitura de documentos não está disponível. Confira o terminal do backend.', 503)
        conteudo = arquivo.file.read(LIMITE_BYTES + 1)
        if len(conteudo) > LIMITE_BYTES:
            raise FalhaGeracao('O arquivo excede o limite de 8 MB.', 413)
        if not conteudo:
            raise FalhaGeracao('O arquivo enviado está vazio.', 422)
        if not vaga_grade.acquire(blocking=False):
            raise FalhaGeracao('Já há um documento sendo lido. Aguarde e tente novamente.', 429)
        try:
            return app.state.grade(conteudo, pergunta)
        finally:
            vaga_grade.release()

    @app.get('/api/v1/evaluation')
    def evaluation():
        try:
            return painel_historico(app.state.rag.info if app.state.rag else None)
        except (OSError, ValueError, KeyError):
            raise FalhaGeracao('Os arquivos da avaliação histórica não estão disponíveis.', 503) from None

    @app.post('/api/v1/multiagent')
    def multiagent(pergunta: Pergunta):
        if app.state.rag is None:
            raise FalhaGeracao('O backend RAG nao esta disponivel.', 503)
        try:
            return OrquestradorMultiagente(app.state.rag).executar(
                pergunta.text, previous_request_id=str(pergunta.previousRequestId)
                if pergunta.previousRequestId is not None else None)
        except (ValueError, OSError, KeyError, TypeError):
            # A pergunta ja foi validada pelo schema (422); o que sobra e configuracao, indice ou disco.
            raise FalhaGeracao('Falha tecnica no fluxo multiagente. Confira configuracao e indice do backend.', 503) from None

    @app.post('/api/v1/comparison/{arm}')
    def comparison(arm: Literal['rag', 'llm', 'multiagente'], pergunta: Pergunta):
        if app.state.comparador is None:
            raise FalhaGeracao('O backend RAG não está disponível.', 503)
        resultado = app.state.comparador.executar(arm, pergunta.text)
        return JSONResponse(resultado, status_code=resultado['technicalStatus'])

    web_dir = Path(os.environ.get('RAG_WEB_DIR', caminho_projeto('../dist'))).resolve()
    if (web_dir / 'index.html').is_file():
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='chat')
    return app


app = create_app()
