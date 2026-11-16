"""Abre e valida uma base publicada sem importar ferramentas de vetorização."""
import json

from rag.config import caminho_projeto
from rag.armazenamento.indice import criar_indice
from rag.armazenamento.manifesto import validar_contrato, hash_bytes


def abrir_indice(config: dict):
    remoto = config['indice'].get('backend') == 'supabase'
    arquivo = caminho_projeto(config['caminhos']['manifesto'])
    if not remoto and not arquivo.exists():
        raise ValueError('Manifesto ausente. Execute 05_indexar.py.')
    if remoto:
        indice = criar_indice(config, config['indice']['colecao'])
        manifesto = indice.manifesto_ativo(config['indice']['colecao'])
    else:
        manifesto = json.loads(arquivo.read_text(encoding='utf-8'))
        indice = criar_indice(config, manifesto['indice']['colecao'])
    validar_contrato(manifesto, config['embeddings'])
    catalogo = caminho_projeto(config['caminhos']['catalogo'])
    if hash_bytes(catalogo.read_bytes()) != manifesto['corpus'].get('sha256_catalogo'):
        raise ValueError('Catálogo/revisões mudaram. Gere chunks e índice novamente.')
    if manifesto['chunking'] != config['chunking']:
        raise ValueError('Configuração de chunking mudou. Gere chunks e índice novamente.')
    chunks = caminho_projeto(config['caminhos']['chunks'])
    if chunks.exists() and hash_bytes(chunks.read_bytes()) != manifesto['corpus']['sha256_chunks']:
        raise ValueError('Os chunks mudaram após a indexação. Execute 05_indexar.py novamente.')
    if manifesto['indice']['distancia'] != config['indice']['distancia']:
        raise ValueError('Distância configurada incompatível com o índice')
    if manifesto['indice']['colecao_logica'] != config['indice']['colecao']:
        raise ValueError('Coleção configurada incompatível com o índice')
    if indice.contar() != manifesto['indice']['total']:
        raise ValueError('Contagem do índice difere do manifesto; reconstrua com 05_indexar.py.')
    return indice, manifesto


def carregar_base_lexical(indice, manifesto, config):
    """Snapshot de textos conferido contra o corpus versionado do aplicativo."""
    trechos = indice.textos()
    arquivo = caminho_projeto(config['caminhos']['chunks'])
    corpus = {c['chunk_id']: c for c in (json.loads(l) for l in arquivo.read_text(
        encoding='utf-8').splitlines() if l.strip())}
    ids = {t['chunk_id'] for t in trechos}
    if len(trechos) != manifesto['indice']['total'] or len(ids) != len(trechos) or ids != set(corpus):
        raise ValueError('Textos remotos não correspondem aos IDs da base publicada')
    campos = ('source_id', 'versao', 'texto', 'status', 'rascunho', 'abrangencia',
              'validade', 'titulo', 'url', 'secoes', 'sha256_original', 'data_revisao')
    for trecho in trechos:
        if any(trecho.get(c) != corpus[trecho['chunk_id']].get(c) for c in campos):
            raise ValueError('Texto ou metadados remotos divergem do corpus versionado')
    return trechos, manifesto
