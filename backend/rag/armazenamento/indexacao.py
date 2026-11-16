"""Orquestra a indexação. Publica o manifesto só após conferir a coleção completa."""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from filelock import FileLock

from rag.config import caminho_projeto
from rag.ingestao.corpus import carregar_corpus
from rag.armazenamento.embeddings import VetorizadorE5, validar_vetores
from rag.armazenamento.indice import criar_indice
from rag.armazenamento.manifesto import contrato_embeddings, gravar_json, hash_bytes, hash_json, versoes_bibliotecas
from rag.armazenamento.leitura import abrir_indice  # Mantém imports dos scripts anteriores.


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
        remoto = config['indice'].get('backend') == 'supabase'
        indice = criar_indice(config, colecao, criar=True)
        manifesto = {
            'schema': 1, 'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'assinatura': assinatura, 'embeddings': contrato, 'bibliotecas': bibliotecas,
            'execucao_embeddings': {k: config['embeddings'][k] for k in ('dispositivo', 'lote', 'threads_cpu')},
            'corpus': corpus, 'chunking': config['chunking'],
            'indice': {'colecao': colecao, 'colecao_logica': config['indice']['colecao'],
                       'distancia': 'cosine', 'total': len(chunks),
                       'backend': 'supabase' if remoto else 'chroma',
                       'caminho': 'Supabase/pgvector' if remoto else config['caminhos']['chroma']},
            'vetores': {'arquivo': str(vetor_path.relative_to(caminho_projeto('.'))).replace('\\', '/'),
                        'sha256': hash_bytes(vetor_path.read_bytes()), 'origem_nesta_execucao': origem,
                        'forma': list(matriz.shape), 'dtype': str(matriz.dtype)},
        }
        if remoto:
            indice.publicar(chunks, matriz, manifesto)
        else:
            indice.atualizar(chunks, matriz, config['indice']['lote'])
        if indice.ids() != {c['chunk_id'] for c in chunks}:
            raise ValueError('A coleção não corresponde aos chunks')
        # Coleções de outras versões ficam preservadas; somente este manifesto aponta a versão ativa.
        gravar_json(manifesto_path.parent / 'manifestos' / f'{assinatura[:20]}.json', manifesto)
        # O manifesto local do Chroma permanece disponível para voltar ao modo local.
        if not remoto:
            gravar_json(manifesto_path, manifesto)
        return manifesto
