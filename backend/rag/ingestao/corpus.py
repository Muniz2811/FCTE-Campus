"""Validação do corpus aprovado antes de gerar vetores ou escrever no índice."""
import json

from rag.ingestao.catalogo import ler_catalogo, fonte_indexavel, validar_catalogo
from rag.config import caminho_projeto
from rag.armazenamento.manifesto import hash_bytes, hash_json
from rag.ingestao.chunking import id_config


def carregar_corpus(config: dict):
    pasta = config['caminhos']
    fontes = ler_catalogo(caminho_projeto(pasta['catalogo']))
    erros = validar_catalogo(fontes, config['catalogo'])
    if erros:
        raise ValueError('\n'.join(map(str, erros)))
    aprovadas = {f['source_id']: f for f in fontes if fonte_indexavel(f)}
    arquivo = caminho_projeto(pasta['chunks'])
    if not arquivo.exists():
        raise ValueError('chunks.jsonl não encontrado. Execute 04_chunks.py sem --rascunho.')
    dados = arquivo.read_bytes()
    chunks = [json.loads(linha) for linha in dados.decode('utf-8').splitlines() if linha.strip()]
    if not chunks:
        raise ValueError('Corpus sem chunks')
    ids = set()
    usadas = set()
    for chunk in chunks:
        sid = chunk['source_id']
        if sid not in aprovadas or chunk.get('status') != 'aprovado' or chunk.get('rascunho') is not False:
            raise ValueError(f'Chunk não aprovado ou de rascunho: {chunk["chunk_id"]}')
        fonte = aprovadas[sid]
        if chunk.get('config_chunking') != id_config(config['chunking'], config['embeddings']):
            raise ValueError('Configuração de chunks mudou. Execute 04_chunks.py.')
        for campo in ('versao', 'titulo', 'url', 'data_revisao', 'revisor', 'validade', 'abrangencia', 'campus', 'limitacoes'):
            if chunk.get(campo) != fonte[campo]:
                raise ValueError(f'Chunk desatualizado ({campo}): {chunk["chunk_id"]}. Gere os chunks novamente.')
        if chunk['sha256_original'] != fonte['sha256']:
            raise ValueError(f'SHA da fonte mudou: {sid}')
        if chunk['chunk_id'] in ids:
            raise ValueError('chunk_id duplicado')
        ids.add(chunk['chunk_id'])
        usadas.add(sid)
    if usadas != set(aprovadas):
        raise ValueError(f'Fontes aprovadas ausentes dos chunks: {sorted(set(aprovadas) - usadas)}')
    if len(usadas) < config['catalogo']['meta_aprovados']:
        raise ValueError('Corpus abaixo da meta de documentos aprovados')
    fontes_manifesto = [{k: f[k] for k in ('source_id', 'titulo', 'url', 'versao', 'sha256',
                                          'data_revisao', 'revisor', 'validade', 'limitacoes')}
                        for f in fontes if f['source_id'] in usadas]
    return chunks, {'sha256_chunks': hash_bytes(dados), 'versao': hash_json(chunks),
                    'sha256_catalogo': hash_bytes(caminho_projeto(pasta['catalogo']).read_bytes()),
                    'total_fontes': len(usadas), 'total_chunks': len(chunks), 'fontes': fontes_manifesto,
                    'aprovadas_no_catalogo': sum(f['status'] == 'aprovado' for f in fontes),
                    'fora_do_indice': [{'source_id': f['source_id'], 'motivo': f['motivo']}
                                      for f in fontes if not fonte_indexavel(f)]}
