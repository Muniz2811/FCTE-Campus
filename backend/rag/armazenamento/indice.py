"""Persistência e consulta de embeddings explícitos no Chroma."""
import json
from datetime import date
from pathlib import Path

import chromadb
from chromadb.config import Settings


def metadados_chunk(chunk: dict) -> dict:
    validade = chunk['validade']
    validade_ord = 99991231 if validade == 'desconhecida' else int(date.fromisoformat(validade).strftime('%Y%m%d'))
    campos = ('source_id', 'versao', 'titulo', 'url', 'campus', 'abrangencia', 'status',
              'data_revisao', 'sha256_original', 'config_chunking', 'validade', 'tokens')
    return {**{campo: chunk[campo] for campo in campos}, 'revisor': chunk.get('revisor', ''),
            'validade_ord': validade_ord, 'rascunho': False,
            'limitacoes': chunk.get('limitacoes', ''),
            'secoes_json': json.dumps(chunk['secoes'], ensure_ascii=False),
            'entidades_json': json.dumps(chunk.get('entidades', []), ensure_ascii=False)}


class IndiceChroma:
    def __init__(self, pasta: Path | str, colecao: str, criar=False):
        if not criar and not (Path(pasta) / 'chroma.sqlite3').exists():
            raise ValueError('Índice não encontrado. Execute 05_indexar.py primeiro.')
        self.cliente = chromadb.PersistentClient(path=str(pasta), settings=Settings(anonymized_telemetry=False))
        if criar:
            self.colecao = self.cliente.get_or_create_collection(
                name=colecao, embedding_function=None,
                configuration={'hnsw': {'space': 'cosine'}},
            )
        else:
            self.colecao = self.cliente.get_collection(name=colecao, embedding_function=None)
        if self.colecao.configuration['hnsw']['space'] != 'cosine':
            raise ValueError('Coleção incompatível: distância precisa ser cosine')

    def contar(self) -> int:
        return self.colecao.count()

    def atualizar(self, chunks: list[dict], vetores, lote: int) -> None:
        if lote <= 0 or len(chunks) != len(vetores):
            raise ValueError('Lote ou quantidade de vetores inválidos')
        # Validar todos os metadados antes da primeira escrita.
        for chunk in chunks:
            if chunk.get('status') != 'aprovado' or chunk.get('rascunho') is not False:
                raise ValueError('Somente chunks aprovados, sem rascunho, podem entrar no índice')
        metadados = [metadados_chunk(chunk) for chunk in chunks]
        ids = [c['chunk_id'] for c in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError('chunk_id duplicado')
        for inicio in range(0, len(chunks), lote):
            fim = inicio + lote
            self.colecao.upsert(ids=ids[inicio:fim], embeddings=vetores[inicio:fim].tolist(),
                                documents=[c['texto'] for c in chunks[inicio:fim]], metadatas=metadados[inicio:fim])
        antigos = set(self.colecao.get(include=[])['ids']) - set(ids)
        if antigos:
            self.colecao.delete(ids=sorted(antigos))

    def consultar(self, vetor, limite: int, data: str) -> list[dict]:
        if limite <= 0 or not self.contar():
            return []
        hoje = int(date.fromisoformat(data).strftime('%Y%m%d'))
        resultado = self.colecao.query(
            query_embeddings=[list(map(float, vetor))], n_results=min(limite, self.contar()),
            where={'$and': [{'status': 'aprovado'}, {'rascunho': False},
                            {'abrangencia': {'$in': ['Gama', 'UnB geral', 'DF']}},
                            {'validade_ord': {'$gte': hoje}}]},
            include=['documents', 'metadatas', 'distances'],
        )
        trechos = []
        for cid, texto, meta, distancia in zip(resultado['ids'][0], resultado['documents'][0],
                                               resultado['metadatas'][0], resultado['distances'][0]):
            meta = dict(meta)
            secoes = json.loads(meta.pop('secoes_json'))
            entidades = json.loads(meta.pop('entidades_json'))
            trechos.append({**meta, 'chunk_id': cid, 'texto': texto, 'distancia': float(distancia),
                           'secoes': secoes, 'entidades': entidades})
        return trechos
