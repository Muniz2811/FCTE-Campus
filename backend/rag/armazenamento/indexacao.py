"""Orquestra a indexação. Publica o manifesto só após conferir a coleção completa."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from filelock import FileLock

from rag.config import caminho_projeto
from rag.ingestao.corpus import carregar_corpus
from rag.armazenamento.embeddings import VetorizadorE5, validar_vetores
from rag.armazenamento.indice import IndiceChroma
from rag.armazenamento.manifesto import contrato_embeddings, gravar_json, hash_bytes, hash_json, versoes_bibliotecas


def _obter_vetores(arquivo: Path, chunks: list[dict], config: dict, assinatura: str):
    ids = [c['chunk_id'] for c in chunks]
    if arquivo.exists():
        with np.load(arquivo, allow_pickle=False) as cache:
            if cache['assinatura'].item() != assinatura or cache['ids'].tolist() != ids:
                raise ValueError('Cache de vetores incompatível com o corpus/modelo')
            matriz = validar_vetores(cache['vetores'], len(chunks), config['dimensao'], config['normalizar'])
        return matriz, 'cache_validado'
    embedder = VetorizadorE5(config)
    matriz = embedder.documentos([c['texto'] for c in chunks], progresso=True)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix('.npz.tmp')
    with temporario.open('wb') as saida:
        np.savez_compressed(saida, vetores=matriz, ids=np.array(ids), assinatura=np.array(assinatura))
    temporario.replace(arquivo)
    return matriz, 'gerados_localmente'


def indexar(config: dict) -> dict:
    if config['indice']['distancia'] != 'cosine':
        raise ValueError('Este pipeline exige distância cosine')
    manifesto_path = caminho_projeto(config['caminhos']['manifesto'])
    manifesto_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(manifesto_path.parent / '.indexacao.lock'), timeout=0):
        chunks, corpus = carregar_corpus(config)
        bibliotecas = versoes_bibliotecas()
        contrato = contrato_embeddings(config['embeddings'])
        identidade = {'schema': 1, 'corpus': corpus['versao'], 'embeddings': contrato,
                      'distancia': 'cosine', 'bibliotecas': bibliotecas}
        assinatura = hash_json(identidade)
        colecao = f"{config['indice']['colecao']}-{assinatura[:20]}"
        vetor_path = manifesto_path.parent / 'vetores' / f'{assinatura[:20]}.npz'
        matriz, origem = _obter_vetores(vetor_path, chunks, config['embeddings'], assinatura)
        indice = IndiceChroma(caminho_projeto(config['caminhos']['chroma']), colecao, criar=True)
        indice.atualizar(chunks, matriz, config['indice']['lote'])
        esperados = {c['chunk_id'] for c in chunks}
        if set(indice.colecao.get(include=[])['ids']) != esperados:
            raise ValueError('A coleção não corresponde aos chunks; manifesto anterior preservado')
        manifesto = {
            'schema': 1, 'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'assinatura': assinatura, 'embeddings': contrato, 'bibliotecas': bibliotecas,
            'execucao_embeddings': {k: config['embeddings'][k] for k in ('dispositivo', 'lote', 'threads_cpu')},
            'corpus': corpus, 'chunking': config['chunking'],
            'indice': {'colecao': colecao, 'colecao_logica': config['indice']['colecao'],
                       'distancia': 'cosine', 'total': indice.contar(), 'caminho': config['caminhos']['chroma']},
            'vetores': {'arquivo': str(vetor_path.relative_to(caminho_projeto('.'))).replace('\\', '/'),
                        'sha256': hash_bytes(vetor_path.read_bytes()), 'origem_nesta_execucao': origem,
                        'forma': list(matriz.shape), 'dtype': str(matriz.dtype)},
        }
        # Coleções de outras versões ficam preservadas; somente este manifesto aponta a versão ativa.
        gravar_json(manifesto_path.parent / 'manifestos' / f'{assinatura[:20]}.json', manifesto)
        gravar_json(manifesto_path, manifesto)
        return manifesto


def abrir_indice(config: dict):
    arquivo = caminho_projeto(config['caminhos']['manifesto'])
    if not arquivo.exists():
        raise ValueError('Manifesto ausente. Execute 05_indexar.py.')
    from rag.armazenamento.manifesto import validar_contrato
    manifesto = json.loads(arquivo.read_text(encoding='utf-8'))
    validar_contrato(manifesto, config['embeddings'])
    catalogo_path = caminho_projeto(config['caminhos']['catalogo'])
    if hash_bytes(catalogo_path.read_bytes()) != manifesto['corpus'].get('sha256_catalogo'):
        raise ValueError('Catálogo/revisões mudaram. Gere chunks e índice novamente.')
    if manifesto['chunking'] != config['chunking']:
        raise ValueError('Configuração de chunking mudou. Gere chunks e índice novamente.')
    chunks_path = caminho_projeto(config['caminhos']['chunks'])
    if chunks_path.exists() and hash_bytes(chunks_path.read_bytes()) != manifesto['corpus']['sha256_chunks']:
        raise ValueError('Os chunks mudaram após a indexação. Execute 05_indexar.py novamente.')
    if manifesto['indice']['distancia'] != config['indice']['distancia']:
        raise ValueError('Distância configurada incompatível com o índice')
    if manifesto['indice']['colecao_logica'] != config['indice']['colecao']:
        raise ValueError('Coleção configurada incompatível com o índice')
    indice = IndiceChroma(caminho_projeto(config['caminhos']['chroma']), manifesto['indice']['colecao'])
    if indice.contar() != manifesto['indice']['total']:
        raise ValueError('Contagem do índice difere do manifesto; reconstrua com 05_indexar.py.')
    return indice, manifesto
