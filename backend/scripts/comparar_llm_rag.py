"""Semana 3: comparação pareada da LLM isolada com o RAG de produção, sem alterá-lo.

Quatro cenários do gabarito existente; primeira saída válida é mantida.
Retentativas somente técnicas. Não julga respostas e não reindexa o corpus.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from rag.consulta.llm_isolada import PROMPT_LIVRE, SaidaLivre, livre
from rag.api import create_app
from rag.config import carregar_config, configurar_cache, caminho_projeto
from rag.consulta.busca import buscar
from rag.consulta.geracao import FalhaGeracao, PROMPT
from rag.consulta.servico import ServicoRAG
from rag.armazenamento.manifesto import gravar_json

ROOT = Path(__file__).resolve().parents[1]

def ler(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grupo(qid):
    n = int(qid[1:])
    return 'T1' if n <= 5 else 'T2' if n <= 10 else 'T3' if n <= 12 else 'T4'



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--pasta', help='Diretório novo ou uma rodada incompleta para retomar')
    parser.add_argument('--max-tentativas', type=int, default=4)
    parser.add_argument('--intervalo', type=float, default=4.5)
    args = parser.parse_args()
    if args.max_tentativas < 1 or args.intervalo < 0:
        parser.error('Parâmetros de execução inválidos')
    env = Path(args.env_file).resolve()
    if not env.is_file():
        parser.error('Arquivo de ambiente não encontrado')
    valores = dotenv_values(env)
    chave = os.environ.get('GEMINI_API_KEY') or valores.get('GEMINI_API_KEY') or ''
    if not chave:
        parser.error('Chave Gemini ausente')
    cfg = carregar_config()
    cfg['geracao']['modelo'] = os.environ.get('GEMINI_MODEL') or valores.get('GEMINI_MODEL') or cfg['geracao']['modelo']
    if not cfg['busca']['reranker']['ativo']:
        parser.error('O experimento exige o RAG atual com reranker ativo')
    configurar_cache(cfg)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    pasta = Path(args.pasta).resolve() if args.pasta else ROOT / 'avaliacao/resultados' / (
        'semana3-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    pasta.mkdir(parents=True, exist_ok=True)
    paths = ['config/rag.yaml', 'data/catalogo/fontes.csv', 'data/chunks/chunks.jsonl', 'data/index/manifesto.json',
             'avaliacao/gabarito.json', 'scripts/comparar_llm_rag.py', *[str(p.relative_to(ROOT)).replace('\\', '/')
              for p in sorted((ROOT/'rag').rglob('*.py'))]]
    hashes = {p: sha(ROOT/p) for p in paths}
    resultados_path = pasta/'execucoes.json'
    if resultados_path.exists():
        registro = ler(resultados_path)
        if registro['hashes_antes'] != hashes or registro['config'] != cfg:
            raise ValueError('Código, configuração ou corpus mudou; iniciar nova rodada')
    else:
        gold = ler(ROOT/'avaliacao/gabarito.json')
        for q in gold['perguntas']:
            q['teste'] = grupo(q['id'])
        gravar_json(pasta/'gabarito.json', gold)
        rng = random.Random(12032026)
        ordem = []
        for q in gold['perguntas']:
            bracos = ['llm', 'rag']
            rng.shuffle(bracos)
            ordem.extend({'qid': q['id'], 'braco': b} for b in bracos)
        registro = {'inicio': datetime.now(timezone.utc).isoformat(), 'data_relatorio_brasilia': '2026-11-12',
                    'natureza': 'Dois sistemas, quatro cenários; sem ablação ou ajuste do RAG.',
                    'config': cfg, 'hashes_antes': hashes, 'manifesto': ler(ROOT/'data/index/manifesto.json'),
                    'prompt_llm': PROMPT_LIVRE, 'prompt_rag': PROMPT,
                    'schema_llm': SaidaLivre.model_json_schema(),
                    'ordem_seed': 12032026, 'ordem': ordem, 'tentativas': [], 'selecionadas': [],
                    'politica': 'Primeira resposta tecnicamente válida, sem repetir erro semântico. Até quatro tentativas por falha técnica.',
                    'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
        gravar_json(resultados_path, registro)
    gold = ler(pasta/'gabarito.json')
    questoes = {q['id']: q for q in gold['perguntas']}
    print(json.dumps({'pasta': str(pasta), 'modelo': cfg['geracao']['modelo'], 'tarefas': len(registro['ordem'])}, ensure_ascii=False), flush=True)
    inicio_carga = time.perf_counter()
    servico = ServicoRAG(cfg, chave)
    warm = buscar(questoes['Q01']['pergunta'], cfg, modelo=servico.modelo)
    registro['aquecimento'] = {'pergunta': questoes['Q01']['pergunta'], 'sem_gemini': True,
                              'segundos': time.perf_counter()-inicio_carga, 'trechos': len(warm['trechos'])}
    gravar_json(resultados_path, registro)
    ultima = 0.0
    with TestClient(create_app(lambda: servico), base_url='http://127.0.0.1') as api, httpx.Client(timeout=cfg['geracao']['timeout_s']) as externo:
        registro['health'] = api.get('/api/v1/health').json()
        for item in registro['ordem']:
            qid, braco = item['qid'], item['braco']
            if any(s['qid'] == qid and s['braco'] == braco and s['status_tecnico'] == 200 for s in registro['selecionadas']):
                continue
            feitas = [t for t in registro['tentativas'] if t['qid'] == qid and t['braco'] == braco]
            for n in range(len(feitas), args.max_tentativas):
                time.sleep(max(0, args.intervalo-(time.perf_counter()-ultima)))
                ultima = time.perf_counter()
                start = datetime.now(timezone.utc).isoformat()
                if braco == 'llm':
                    resultado = livre(externo, chave, cfg['geracao'], questoes[qid]['pergunta'])
                else:
                    logs = caminho_projeto(cfg['caminhos']['execucoes'])
                    antes = set(logs.glob('chat-*.json'))
                    response = api.post('/api/v1/chat', json={'text': questoes[qid]['pergunta'], 'campus': 'gama'})
                    resultado = {'status_tecnico': response.status_code}
                    if response.status_code == 200:
                        resultado['resposta'] = response.json()
                        log = logs/f'chat-{response.json()["requestId"]}.json'
                    else:
                        resultado['erro'] = response.json().get('detail', 'Falha na API local')
                        novos = sorted(set(logs.glob('chat-*.json'))-antes)
                        log = novos[-1] if novos else None
                    if log is not None and log.exists():
                        resultado['log_backend'] = ler(log)
                tentativa = {'qid': qid, 'teste': grupo(qid), 'braco': braco, 'tentativa': n+1,
                             'inicio': start, 'segundos': time.perf_counter()-ultima, **resultado}
                registro['tentativas'].append(tentativa)
                gravar_json(resultados_path, registro)
                print(json.dumps({k: tentativa.get(k) for k in ('qid','teste','braco','tentativa','status_tecnico','segundos')}, ensure_ascii=False), flush=True)
                if tentativa['status_tecnico'] == 200:
                    registro['selecionadas'] = [s for s in registro['selecionadas'] if not (s['qid']==qid and s['braco']==braco)]
                    registro['selecionadas'].append(tentativa)
                    gravar_json(resultados_path, registro)
                    break
                if tentativa['status_tecnico'] not in (429, 500, 502, 503, 504):
                    break
                if n+1 < args.max_tentativas:
                    time.sleep(min(45, 5*2**n))
    registro['hashes_depois'] = {p: sha(ROOT/p) for p in paths}
    registro['configuracao_preservada'] = registro['hashes_antes'] == registro['hashes_depois']
    registro['fim'] = datetime.now(timezone.utc).isoformat()
    gravar_json(resultados_path, registro)
    print(json.dumps({'concluidas': len(registro['selecionadas']), 'tarefas': len(registro['ordem']),
                      'preservada': registro['configuracao_preservada'], 'pasta': str(pasta)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
