"""Carrega a configuração central (config/rag.yaml)."""

from pathlib import Path
import os

import yaml
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
CONFIG_PADRAO = RAIZ / "config" / "rag.yaml"


def carregar_config(caminho: Path | str | None = None) -> dict:
    caminho = Path(caminho) if caminho else CONFIG_PADRAO
    with open(caminho, encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo)
    ambiente = ambiente_backend()
    config['indice']['backend'] = ambiente.get('RAG_INDEX_BACKEND') or config['indice'].get('backend', 'chroma')
    if config['indice']['backend'] not in ('chroma', 'supabase'):
        raise ValueError('RAG_INDEX_BACKEND deve ser chroma ou supabase')
    config['perfil'] = ambiente.get('RAG_PROFILE') or 'full'
    if config['perfil'] not in ('full', 'light'):
        raise ValueError('RAG_PROFILE deve ser full ou light')
    if config['perfil'] == 'light':
        if config['indice']['backend'] != 'supabase':
            raise ValueError('O perfil light exige RAG_INDEX_BACKEND=supabase')
        config['busca']['metodo'] = 'bm25'
        config['busca']['reranker']['ativo'] = False
    return config


def ambiente_backend() -> dict:
    """Ambiente do processo prevalece sobre backend/.env. Nunca serializar este retorno."""
    arquivo = Path(os.environ.get('RAG_ENV_FILE') or RAIZ / '.env')
    valores = dotenv_values(arquivo) if arquivo.is_file() else {}
    return {**valores, **os.environ}


def caminho_projeto(relativo: str) -> Path:
    """Transforma um caminho do rag.yaml (relativo à raiz) em caminho absoluto."""
    return RAIZ / relativo


def configurar_cache(config: dict) -> None:
    """Cache isolado; HF_HOME externo (ex.: volume Docker) tem prioridade."""
    os.environ.setdefault('HF_HOME', str(caminho_projeto(config['embeddings'].get('cache', '.cache/huggingface'))))
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
