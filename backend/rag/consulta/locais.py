"""Consultas exatas ao inventário cartográfico curado, sem inferência da LLM."""
import json
import re
import unicodedata
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from rag.config import caminho_projeto
from rag.ingestao.catalogo import ler_catalogo, fonte_indexavel
from rag.armazenamento.manifesto import hash_bytes


class PedidoNavegacao(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operacao: Literal['listar', 'contar', 'proximidade', 'rota']
    categoria: str | None = Field(default=None, max_length=30)
    predio_id: str | None = Field(default=None, pattern=r'^[a-z0-9-]{1,60}$')
    andar: int | None = Field(default=None, ge=-5, le=40)
    nome: str | None = Field(default=None, max_length=200)
    acessivel: bool = False


class LocalNavegacao(BaseModel):
    predio_id: str
    predio: str
    ambiente_id: str
    nome: str
    andar: int
    andar_nome: str
    categoria: str
    fonte_n: int


class PlanoNavegacao(BaseModel):
    operacao: Literal['listar', 'contar', 'proximidade', 'rota']
    locais: list[LocalNavegacao] = Field(max_length=300)
    total: int
    acessivel: bool = False


def _termos(texto):
    normal = ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold())
                     if not unicodedata.combining(c))
    sinonimos = {'lab': 'laboratorio', 'laboratorios': 'laboratorio', 'labs': 'laboratorio'}
    return {sinonimos.get(t, t) for t in re.findall(r'[a-z0-9]+', normal) if t not in {'de', 'da', 'do', 'das', 'dos'}}


def consultar_locais(pedido: PedidoNavegacao, config: dict, base_version: str) -> dict:
    fontes = {f['source_id']: f for f in ler_catalogo(caminho_projeto(config['caminhos']['catalogo']))
              if fonte_indexavel(f)}
    chunks = [json.loads(l) for l in caminho_projeto(config['caminhos']['chunks']).read_text(
        encoding='utf-8').splitlines() if l.strip()]
    candidatos = []
    for arquivo in sorted(caminho_projeto('data/imports/mapas').glob('MAP-*.json')):
        dados = arquivo.read_bytes()
        ficha = json.loads(dados)
        fonte = fontes.get(ficha['source_id'])
        if fonte is None or fonte['sha256'] != hash_bytes(dados):
            raise ValueError('Ficha do mapa ausente do catálogo ou com hash divergente')
        if pedido.predio_id and ficha['predio_id'] != pedido.predio_id:
            continue
        if pedido.andar is not None and ficha['andar']['nivel'] != pedido.andar:
            continue
        for a in ficha['ambientes']:
            if pedido.categoria and a['categoria'] != pedido.categoria:
                continue
            if pedido.nome:
                termos = _termos(pedido.nome)
                if not termos or not (termos <= _termos(a['nome']) or termos == _termos(a['id'])):
                    continue
            marcador = f'identificador no mapa: {a["id"]}'
            trecho = next((c for c in chunks if c['source_id'] == fonte['source_id'] and marcador in c['texto']), None)
            if trecho is None:
                raise ValueError('Ambiente sem trecho rastreável no corpus')
            candidatos.append(({'predio_id': ficha['predio_id'], 'predio': ficha['predio'],
                                'ambiente_id': a['id'], 'nome': a['nome'], 'andar': a['andar'],
                                'andar_nome': ficha['andar']['nome'], 'categoria': a['categoria']}, trecho))
    if len(candidatos) > 300:
        raise ValueError('Inventário excede o limite do contrato de navegação')
    # Uma citação por ficha: o link leva ao inventário completo, não só ao top-5 semântico.
    referencias, por_fonte, locais = [], {}, []
    for local, trecho in candidatos:
        sid = trecho['source_id']
        if sid not in por_fonte:
            n = len(referencias) + 1
            por_fonte[sid] = n
            fonte = fontes[sid]
            # Unidade documental estruturada; não atribuir o inventário inteiro a um chunk vetorial.
            referencias.append({'n': n, 'doc_id': sid, 'chunk_id': f'map_{sid.lower()}_{fonte["sha256"][:16]}',
                'titulo': fonte['titulo'], 'orgao': 'Inventário cartográfico curado · Grupo 09',
                'pagina': None, 'secao': 'Inventário completo de ambientes por andar',
                'url': fonte['url'], 'versao': fonte['versao'],
                'trecho': '\n'.join(f"{l['nome']} ({l['ambiente_id']}), {l['andar_nome']} da {l['predio']}."
                                    for l, t in candidatos if t['source_id'] == sid),
                'data_revisao': fonte['data_revisao'], 'validade': fonte['validade']})
        locais.append(local | {'fonte_n': por_fonte[sid]})
    citacoes = ' '.join(f'[{f["n"]}]' for f in referencias)
    if not locais:
        texto = 'Não encontrei ambientes com esses critérios no inventário curado. Posso consultar o mapa local.'
    elif pedido.operacao == 'contar':
        texto = f'O inventário curado registra **{len(locais)}** ambientes que atendem ao pedido. {citacoes}'
        por_andar = {}
        for local in locais:
            chave = (local['predio'], local['andar_nome'])
            por_andar[chave] = por_andar.get(chave, 0) + 1
        texto += '\n\n' + '\n'.join(f'- {predio}, {andar}: **{total}**.' for (predio, andar), total in por_andar.items())
    else:
        texto = f'Encontrei **{len(locais)}** ambientes no inventário curado. {citacoes}'
    return {'grupo': 'grupo09', 'status': 'answered' if locais else 'insufficient',
            'encontrou_base': bool(locais), 'resposta': texto, 'fontes': referencias,
            'afirmacoes': [], 'trechos': referencias, 'request_id': str(uuid4()),
            'base_version': base_version, 'modelo': None, 'backend': 'inventario_curado',
            'tempo_ms': 0, 'navegacao': PlanoNavegacao(operacao=pedido.operacao, locais=locais,
                total=len(locais), acessivel=pedido.acessivel).model_dump()}
