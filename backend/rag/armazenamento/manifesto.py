"""Identidade reproduzível do corpus, modelo e índice."""
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path


def contrato_embeddings(config: dict) -> dict:
    campos = ('modelo', 'revisao', 'dimensao', 'max_tokens', 'prefixo_documento', 'prefixo_pergunta', 'normalizar')
    return {campo: config[campo] for campo in campos}


def validar_contrato(manifesto: dict, config: dict) -> None:
    if manifesto.get('embeddings') != contrato_embeddings(config):
        raise ValueError('Modelo/configuração incompatível com o índice. Gere um novo índice com 05_indexar.py.')


def hash_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def hash_json(dados) -> str:
    return hash_bytes(json.dumps(dados, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + '.tmp')
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporario.replace(caminho)


def versoes_bibliotecas() -> dict:
    nomes = ('sentence-transformers', 'transformers', 'tokenizers', 'torch', 'chromadb', 'numpy')
    return {'python': platform.python_version(), **{nome: version(nome) for nome in nomes}}
