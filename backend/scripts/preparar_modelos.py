"""Baixa a revisão fixa do reranker; não chama Gemini nem altera o Chroma."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from huggingface_hub import snapshot_download
from rag.config import carregar_config, caminho_projeto


def main():
    cfg = carregar_config()['busca']['reranker']
    destino = caminho_projeto('.cache/reranker')
    snapshot_download(cfg['modelo'], revision=cfg['revisao'], local_dir=destino,
        allow_patterns=['config.json', 'tokenizer*', 'special_tokens_map.json',
                        'sentencepiece.bpe.model', 'model.safetensors'], max_workers=1)
    (destino / 'revision.txt').write_text(cfg['revisao'], encoding='utf-8')
    print('Reranker preparado:', cfg['modelo'], cfg['revisao'])


if __name__ == '__main__':
    main()
