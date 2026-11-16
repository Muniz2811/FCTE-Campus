"""Executa de forma SEQUENCIAL Gemini, RAG e multiagente.

Exemplo (raiz do repositorio):
  .\\backend\\.venv\\Scripts\\python.exe backend/scripts/comparar_tres_modos.py --env-file backend/.env --conjunto conferencia

Nao faz julgamento de qualidade. Preserva TODAS as tentativas e erros tecnicos.
"""
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag.config import carregar_config, configurar_cache
from rag.consulta.servico import ServicoRAG
from rag.consulta.comparacao import Comparador
from rag.armazenamento.manifesto import gravar_json
from rag.consulta.multiagente import PROMPT_PESQUISADOR, PROMPT_REDATOR, PROMPT_REVISOR
from rag.consulta.llm_isolada import PROMPT_LIVRE
from rag.consulta.geracao import PROMPT

BRACOS = ('llm', 'rag', 'multiagente')


def ler(arquivo):
    return json.loads(Path(arquivo).read_text(encoding='utf-8'))


def hash_file(arquivo):
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--conjunto', choices=['desenvolvimento', 'conferencia'], default='conferencia')
    parser.add_argument('--pasta', help='Pasta de resultados nova ou usada para retomar')
    parser.add_argument('--max-tentativas', type=int, default=3)
    parser.add_argument('--intervalo', type=float, default=4.5)
    args = parser.parse_args()
    if args.max_tentativas < 1 or args.intervalo < 0:
        parser.error('Tentativas e intervalo invalidos')
    env = Path(args.env_file).resolve()
    if not env.is_file():
        parser.error('Arquivo .env nao encontrado')
    settings = dotenv_values(env)
    chave = os.environ.get('GEMINI_API_KEY') or settings.get('GEMINI_API_KEY') or ''
    if not chave:
        parser.error('GEMINI_API_KEY ausente')
    cfg = carregar_config()
    cfg['geracao']['modelo'] = os.environ.get('GEMINI_MODEL') or settings.get('GEMINI_MODEL') or cfg['geracao']['modelo']
    configurar_cache(cfg)
    referencia = ROOT / 'avaliacao' / ('conferencia_final.json' if args.conjunto == 'conferencia' else 'gabarito.json')
    monitored = ['config/rag.yaml', 'data/catalogo/fontes.csv', 'data/chunks/chunks.jsonl',
                 'data/index/manifesto.json', str(referencia.relative_to(ROOT)),
                 *[str(p.relative_to(ROOT)).replace('\\', '/') for p in sorted((ROOT/'rag').rglob('*.py'))]]
    hashes = {p: hash_file(ROOT / p) for p in monitored}
    folder = Path(args.pasta).resolve() if args.pasta else ROOT/'avaliacao'/'resultados'/(
        'tres-modos-'+args.conjunto+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(parents=True, exist_ok=True)
    arquivo = folder / 'execucoes.json'
    if arquivo.exists():
        dados = ler(arquivo)
        if dados['hashes_antes'] != hashes or dados['conjunto'] != args.conjunto or dados['config'] != cfg:
            raise ValueError('Codigo, base ou configuracao mudaram: inicie uma nova rodada')
    else:
        gold = ler(referencia)
        if len({q['id'] for q in gold['perguntas']}) != len(gold['perguntas']):
            raise ValueError('IDs duplicados')
        gravar_json(folder/'gabarito.json', gold)
        ordem = [{'qid':q['id'], 'braco': arm} for q in gold['perguntas'] for arm in BRACOS]
        random.Random(16112026).shuffle(ordem)
        dados = {
            'inicio': datetime.now(timezone.utc).isoformat(), 'conjunto':args.conjunto,
            'natureza':gold.get('natureza', '15 questoes conhecidas usadas no desenvolvimento'),
            'config':cfg, 'hashes_antes':hashes, 'modelo':cfg['geracao']['modelo'],
            'manifesto':ler(ROOT/'data/index/manifesto.json'),
            'promptSha256':{nome: hashlib.sha256(prompt.encode('utf-8')).hexdigest() for nome,prompt in
                [('llm',PROMPT_LIVRE),('rag',PROMPT),('pesquisador',PROMPT_PESQUISADOR),
                 ('redator',PROMPT_REDATOR),('revisor',PROMPT_REVISOR)]},
            'historico':'Sem historico de conversa entre questoes; perguntas independentes.',
            'politica':'Primeiro resultado tecnicamente valido; repetir apenas erros transitorios; preservar todas as chamadas.',
            'ordem':ordem, 'tentativas':[], 'selecionadas':[],
            'gitHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        }
        gravar_json(arquivo,dados)
    questoes = {q['id']:q for q in ler(folder/'gabarito.json')['perguntas']}
    servico = ServicoRAG(cfg,chave)
    comparador = Comparador(servico)
    try:
        dados['health'] = servico.info
        gravar_json(arquivo,dados)
        for item in dados['ordem']:
            qid,arm = item['qid'],item['braco']
            if any(s['qid']==qid and s['braco']==arm for s in dados['selecionadas']):
                continue
            tentativas = [t for t in dados['tentativas'] if t['qid']==qid and t['braco']==arm]
            for indice in range(len(tentativas), args.max_tentativas):
                time.sleep(args.intervalo)
                inicio = time.monotonic()
                resposta = comparador.executar(arm,questoes[qid]['pergunta'])
                tentativa = {'qid':qid,'braco':arm,'tentativa':indice+1,
                    'inicio':datetime.now(timezone.utc).isoformat(),
                    'segundos_wall':round(time.monotonic()-inicio,4),
                    **resposta}
                dados['tentativas'].append(tentativa)
                if resposta['technicalStatus']==200:
                    dados['selecionadas'].append(tentativa)
                gravar_json(arquivo,dados)
                print(f'{qid} {arm} tentativa {indice+1}: {resposta["technicalStatus"]}',flush=True)
                if resposta['technicalStatus']==200 or resposta['technicalStatus'] not in (429,500,502,503,504):
                    break
                if indice+1 < args.max_tentativas:
                    time.sleep(min(30,2**indice * 5))
    finally:
        servico.close()
        dados['fim'] = datetime.now(timezone.utc).isoformat()
        dados['hashes_depois']={p:hash_file(ROOT/p) for p in monitored}
        dados['configuracao_preservada']=dados['hashes_depois']==dados['hashes_antes']
        dados['concluidas']=len(dados['selecionadas'])
        dados['esperadas']=len(dados['ordem'])
        gravar_json(arquivo,dados)
        print(json.dumps({'pasta':str(folder),'completas':dados['concluidas'],
                          'esperadas':dados['esperadas'],'hashes_preservados':dados['configuracao_preservada']}))


if __name__=='__main__':
    main()
