"""Gera embeddings E5 e publica no armazenamento configurado."""
import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import carregar_config, configurar_cache
from rag.armazenamento.indexacao import indexar


def main():
    config = carregar_config()
    configurar_cache(config)
    try:
        manifesto = indexar(config)
    except (ValueError, OSError) as erro:
        print(f'Não foi possível indexar: {erro}', file=sys.stderr)
        return 1
    print(f"Fontes aprovadas: {manifesto['corpus']['aprovadas_no_catalogo']}")
    print(f"Fontes indexadas: {manifesto['corpus']['total_fontes']}")
    print(f"Chunks/vetores: {manifesto['indice']['total']} × {manifesto['embeddings']['dimensao']}")
    print(f"Coleção ativa: {manifesto['indice']['colecao']} (cosine)")
    print(f"Vetores: {manifesto['vetores']['origem_nesta_execucao']}")
    print(f"Armazenamento: {config['indice'].get('backend', 'chroma')}")
    print('Manifesto: Supabase' if config['indice'].get('backend') == 'supabase'
          else f"Manifesto: {config['caminhos']['manifesto']}")
    for fonte in manifesto['corpus']['fora_do_indice']:
        print(f"Fora do índice: {fonte['source_id']} — {fonte['motivo']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
