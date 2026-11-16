"""Adaptador v1 do contrato /perguntar, sem dependência da recuperação interna."""
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from rag.consulta.locais import PedidoNavegacao, PlanoNavegacao


class ContextoIntegracao(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    campus: Literal['gama'] = 'gama'
    data: date | None = None
    curso: str | None = Field(default=None, max_length=60)
    previous_request_id: UUID | None = None
    navegacao: PedidoNavegacao | None = None


class PerguntaIntegracao(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    pergunta: str = Field(min_length=1, max_length=1000)
    contexto: ContextoIntegracao = Field(default_factory=ContextoIntegracao)
    max_trechos: int = Field(default=5, ge=1, le=20)


class FonteIntegracao(BaseModel):
    n: int = Field(ge=1)
    doc_id: str
    chunk_id: str
    titulo: str
    orgao: str
    pagina: int | None = None
    secao: str | None = None
    url: str | None = None
    versao: str
    trecho: str
    data_revisao: str | None = None
    validade: str | None = None


class AfirmacaoIntegracao(BaseModel):
    texto: str
    chunk_ids: list[str]


class RespostaIntegracao(BaseModel):
    contrato_versao: Literal['1.0'] = '1.0'
    grupo: Literal['grupo09'] = 'grupo09'
    dominio: Literal['servicos_infraestrutura'] = 'servicos_infraestrutura'
    status: Literal['answered', 'insufficient', 'unavailable']
    resposta: str
    encontrou_base: bool
    fontes: list[FonteIntegracao]
    afirmacoes: list[AfirmacaoIntegracao]
    trechos: list[FonteIntegracao]
    request_id: UUID
    base_version: str | None
    modelo: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    max_trechos_aplicado: int | None = None
    tempo_ms: int
    indisponivel: bool = False
    status_http: int | None = None
    retrieval_profile: str | None = None
    retrieval_method: str | None = None
    reranker_enabled: bool | None = None
    backend: str | None = None
    navegacao: PlanoNavegacao | None = None


def fonte_integracao(fonte, n):
    return {'n': n, 'doc_id': fonte.get('sourceId', fonte['id']), 'chunk_id': fonte['id'],
            'titulo': fonte['title'], 'orgao': 'Base curada FCTE · Grupo 09',
            'pagina': None, 'secao': fonte.get('section'), 'url': fonte.get('url'),
            'versao': fonte['version'], 'trecho': fonte['excerpt'],
            'data_revisao': fonte.get('reviewedAt'), 'validade': fonte.get('validUntil')}


def resposta_integracao(resposta, tempo_ms, limite):
    fontes = [fonte_integracao(f, i) for i, f in enumerate(resposta.get('sources', []), 1)]
    return {'contrato_versao': '1.0', 'grupo': 'grupo09',
            'dominio': 'servicos_infraestrutura', 'status': resposta['status'],
            'resposta': resposta.get('answer') or resposta.get('message', ''),
            'encontrou_base': resposta['status'] == 'answered' and bool(fontes), 'fontes': fontes,
            'afirmacoes': [{'texto': c['text'], 'chunk_ids': c['sourceIds']} for c in resposta.get('claims', [])],
            'trechos': [fonte_integracao(t, i) for i, t in enumerate(resposta.get('retrieved', []), 1)],
            'request_id': resposta.get('requestId', str(uuid4())), 'base_version': resposta.get('baseVersion'),
            'modelo': resposta.get('model'), 'usage': resposta.get('usage', {}),
            'retrieval_profile': resposta.get('retrievalProfile'),
            'retrieval_method': resposta.get('retrievalMethod'),
            'reranker_enabled': resposta.get('rerankerEnabled'),
            'max_trechos_aplicado': limite, 'tempo_ms': tempo_ms}


def indisponivel(mensagem, status_http, tempo_ms):
    return {'contrato_versao': '1.0', 'grupo': 'grupo09', 'dominio': 'servicos_infraestrutura',
            'status': 'unavailable', 'indisponivel': True, 'resposta': mensagem,
            'encontrou_base': False, 'fontes': [], 'afirmacoes': [], 'trechos': [],
            'request_id': str(uuid4()), 'base_version': None, 'status_http': status_http, 'tempo_ms': tempo_ms}
