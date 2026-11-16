"""Prepara modelos locais sem acessar Gemini ou o banco vetorial."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import carregar_config, caminho_projeto, configurar_cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--incluir-e5', action='store_true', help='preparar também o E5 para execução offline')
    args = parser.parse_args()
    config = carregar_config()
    if config.get('perfil') == 'light':
        print('Perfil light: BM25 usa textos do Supabase, sem modelos locais para preparar.')
        return
    # Definir HF_HOME antes de importar o Hub, que captura esse caminho no import.
    configurar_cache(config)
    from huggingface_hub import snapshot_download
    cfg = config['busca']['reranker']
    destino = caminho_projeto('.cache/reranker')
    snapshot_download(cfg['modelo'], revision=cfg['revisao'], local_dir=destino,
        allow_patterns=['config.json', 'tokenizer*', 'special_tokens_map.json',
                        'sentencepiece.bpe.model', 'model.safetensors'], max_workers=1)
    (destino / 'revision.txt').write_text(cfg['revisao'], encoding='utf-8')
    print('Reranker preparado:', cfg['modelo'], cfg['revisao'])
    if args.incluir_e5:
        from rag.armazenamento.embeddings import VetorizadorE5
        modelo = VetorizadorE5(config['embeddings'])
        vetor = modelo.pergunta('Preparação do modelo para consulta ao campus Gama')
        print('E5 preparado:', config['embeddings']['modelo'], 'dimensão:', len(vetor))


if __name__ == '__main__':
    main()
