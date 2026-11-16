"""Simula ou publica os vetores locais existentes. Não refaz embeddings nem chama Gemini."""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from rag.config import carregar_config, caminho_projeto
from rag.armazenamento.embeddings import validar_vetores
from rag.armazenamento.indexacao import abrir_indice
from rag.armazenamento.manifesto import hash_bytes
from rag.armazenamento.supabase import IndiceSupabase


def preparar(config):
    local = deepcopy(config)
    local['indice']['backend'] = 'chroma'
    indice, manifesto = abrir_indice(local)
    arquivo = caminho_projeto(manifesto['vetores']['arquivo'])
    if hash_bytes(arquivo.read_bytes()) != manifesto['vetores']['sha256']:
        raise ValueError('Cache de vetores difere do manifesto; migração interrompida')
    chunks = [json.loads(linha) for linha in caminho_projeto(config['caminhos']['chunks']).read_text(
        encoding='utf-8').splitlines() if linha.strip()]
    with np.load(arquivo, allow_pickle=False) as cache:
        ids = cache['ids'].tolist()
        if cache['assinatura'].item() != manifesto['assinatura']:
            raise ValueError('Assinatura do cache incompatível')
        vetores = validar_vetores(cache['vetores'], len(chunks), config['embeddings']['dimensao'])
    if ids != [c['chunk_id'] for c in chunks] or set(ids) != indice.ids():
        raise ValueError('IDs/ordem do corpus, cache e Chroma não correspondem')
    manifesto = deepcopy(manifesto)
    manifesto['indice'].update(backend='supabase', caminho='Supabase/pgvector')
    return chunks, vetores, manifesto


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument('--enviar', action='store_true', help='publicar e trocar a coleção ativa')
    modos.add_argument('--preparar', action='store_true', help='enviar snapshot sem trocar a coleção ativa')
    args = parser.parse_args()
    try:
        chunks, vetores, manifesto = preparar(carregar_config())
        if args.enviar or args.preparar:
            remoto = IndiceSupabase(manifesto['indice']['colecao'])
            if args.preparar:
                remoto.preparar_snapshot(chunks, vetores, manifesto)
            else:
                remoto.publicar(chunks, vetores, manifesto)
            if remoto.ids() != {c['chunk_id'] for c in chunks} or remoto.contar() != len(chunks):
                raise ValueError('Contagem/IDs remotos diferentes do snapshot enviado')
            if remoto.manifesto()['assinatura'] != manifesto['assinatura']:
                raise ValueError('Assinatura remota diferente do snapshot enviado')
        modo = 'snapshot_preparado_sem_trocar_ativo' if args.preparar else (
            'enviado_e_conferido' if args.enviar else 'simulacao_sem_rede')
        print(json.dumps({'modo': modo,
                          'fontes': manifesto['corpus']['total_fontes'], 'chunks': len(chunks),
                          'dimensao': int(vetores.shape[1]), 'colecao': manifesto['indice']['colecao'],
                          'assinatura': manifesto['assinatura'], 'chroma_local_preservado': True},
                         ensure_ascii=False, indent=2))
        if not args.enviar and not args.preparar:
            print('Nada enviado. Siga backend/supabase/README.md e repita com --enviar.')
        return 0
    except (ValueError, OSError, KeyError) as erro:
        print(f'Migração não concluída: {erro}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
