"""Experimento real e explícito do chat; não é teste unitário nem altera o índice.

Retentativas opcionais somente para falhas técnicas, preservando todas as chamadas.
A primeira resposta válida é julgada, inclusive quando incorreta ou insuficiente.
O julgamento semântico exige leitura por avaliador identificado.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

RAIZ = Path(__file__).resolve().parents[1]


def ler(caminho):
    return json.loads(caminho.read_text(encoding='utf-8'))


def sha(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def gravar(caminho, dados):
    temporario = caminho.with_suffix('.tmp')
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporario.replace(caminho)


def executar(args):
    gabarito_path = RAIZ / 'avaliacao/gabarito.json'
    gabarito = ler(gabarito_path)
    pasta = Path(args.retomar).resolve() if args.retomar else (
        RAIZ / 'avaliacao/resultados' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if args.retomar:
        registro = ler(pasta / 'execucoes.json')
        congelados = registro['hashes_antes']
        if any(sha(RAIZ / p) != h for p, h in congelados.items()):
            raise ValueError('Configuração/base mudou: inicie outra rodada')
        if registro['endpoint'] != args.endpoint:
            raise ValueError('Retome usando o mesmo endpoint')
        gabarito = ler(pasta / 'gabarito.json')
    else:
        pasta.mkdir(parents=True, exist_ok=False)
    # Preservar também os bytes, para a cópia ter exatamente o hash pré-execução.
    if not args.retomar:
        (pasta / 'gabarito.json').write_bytes(gabarito_path.read_bytes())
    manifesto = RAIZ / 'data/index/manifesto.json'
    atuais = {p: sha(RAIZ / p) for p in (
        'avaliacao/gabarito.json', 'config/rag.yaml', 'data/catalogo/fontes.csv',
        'data/chunks/chunks.jsonl', 'data/index/manifesto.json',
        'rag/consulta/geracao.py', 'rag/consulta/busca.py',
        'rag/consulta/busca_lexical.py', 'rag/consulta/reranking.py', 'rag/consulta/conversa.py',
        'rag/consulta/servico.py', 'rag/api.py', 'scripts/avaliar_rag.py')}
    if not args.retomar:
        congelados = atuais
        gravar(pasta / 'configuracao.json', {
            'manifesto': ler(manifesto),
            'arquivos': {p: (RAIZ / p).read_text(encoding='utf-8') for p in congelados
                         if p.startswith(('config/', 'rag/', 'scripts/'))},
            'hashes': congelados})
        registro = {'inicio': datetime.now(timezone.utc).isoformat(),
                    'protocolo': 'Primeiro HTTP 200 válido por pergunta; repetir somente falhas técnicas. '
                                 'Não repetir respostas por erro semântico ou insuficiência. Preservar cada tentativa.',
                    'endpoint': args.endpoint, 'hashes_antes': congelados,
                    'manifesto': ler(manifesto), 'execucoes': [], 'tentativas': []}
    registro.setdefault('retomadas', []).append({'em': datetime.now(timezone.utc).isoformat(),
        'max_tentativas_por_questao': args.max_tentativas, 'intervalo_s': args.intervalo})
    with httpx.Client(timeout=110, trust_env=False) as cliente:
        health = cliente.get(args.endpoint.rsplit('/', 1)[0] + '/health')
        health.raise_for_status()
        registro['health'] = health.json()
        if registro['health']['baseVersion'] != registro['manifesto']['assinatura']:
            raise ValueError('API e índice em disco têm versões diferentes')
        gravar(pasta / 'execucoes.json', registro)
        print(f'Pasta da execução: {pasta.relative_to(RAIZ)}', flush=True)
        for pergunta in gabarito['perguntas']:
            feitas = [e for e in registro['tentativas'] if e['id'] == pergunta['id']]
            if any(e.get('http_status') == 200 for e in feitas):
                continue
            if any(sha(RAIZ / p) != h for p, h in congelados.items()):
                raise ValueError('Configuração/base mudou durante o experimento')
            for tentativa in range(len(feitas) + 1, args.max_tentativas + 1):
                anteriores = set((RAIZ / 'data/execucoes').glob('chat-*.json'))
                inicio = time.perf_counter()
                item = {'id': pergunta['id'], 'pergunta': pergunta['pergunta'], 'tentativa': tentativa,
                        'inicio': datetime.now(timezone.utc).isoformat()}
                try:
                    resposta = cliente.post(args.endpoint, json={'text': pergunta['pergunta'], 'campus': 'gama'})
                    item['http_status'] = resposta.status_code
                    item['resposta'] = resposta.json()
                except (httpx.HTTPError, ValueError) as erro:
                    item['erro_transporte'] = type(erro).__name__
                item['duracao_s'] = round(time.perf_counter() - inicio, 3)
                novos = set((RAIZ / 'data/execucoes').glob('chat-*.json')) - anteriores
                logs = [ler(p) for p in novos]
                logs = [log for log in logs if log.get('pergunta') == pergunta['pergunta']]
                if len(logs) == 1:
                    item['log_backend'] = logs[0]
                registro['tentativas'].append(item)
                registro['execucoes'] = [e for e in registro['execucoes'] if e['id'] != pergunta['id']]
                registro['execucoes'].append(item)
                gravar(pasta / 'execucoes.json', registro)
                print(f"{item['id']} tentativa {tentativa}: HTTP {item.get('http_status', 'erro')} | "
                      f"{item.get('resposta', {}).get('status', 'sem resposta')} | {item['duracao_s']}s", flush=True)
                if item.get('http_status') == 200:
                    if not item.get('log_backend'):
                        raise ValueError('Resposta recebida sem log inequívoco; preserve e confira antes de julgar')
                    break
                if item.get('http_status') not in (None, 429, 502, 503, 504) and 'erro_transporte' not in item:
                    break
                if tentativa < args.max_tentativas:
                    time.sleep(min(60, args.intervalo * tentativa))
            if pergunta != gabarito['perguntas'][-1]:
                time.sleep(args.intervalo)
    registro['fim'] = datetime.now(timezone.utc).isoformat()
    registro['hashes_depois'] = {p: sha(RAIZ / p) for p in congelados}
    registro['configuracao_preservada'] = registro['hashes_antes'] == registro['hashes_depois']
    registro['concluida'] = len(registro['execucoes']) == len(gabarito['perguntas']) and all(
        e.get('http_status') == 200 for e in registro['execucoes'])
    gravar(pasta / 'execucoes.json', registro)


def razao(n, d, meta=None):
    valor = n / d if d else None
    return {'numerador': n, 'denominador': d, 'valor': valor, 'meta': meta,
            'atingiu_meta': valor >= meta if valor is not None and meta is not None else None}


def conferir_persistencia(args):
    pasta = Path(args.pasta).resolve()
    manifesto = RAIZ / 'data/index/manifesto.json'
    antes = sha(manifesto)
    ambiente = {**os.environ, 'PYTHONPATH': str(RAIZ), 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'PYTHONIOENCODING': 'utf-8'}
    comandos = [
        [sys.executable, 'scripts/06_conferir.py'],
        [sys.executable, 'scripts/perguntar.py', 'Em qual prédio, andar e sala fica o laboratório COSMOS?', '--json'],
    ]
    provas = []
    for comando in comandos:
        resultado = subprocess.run(comando, cwd=RAIZ, env=ambiente, capture_output=True,
                                   encoding='utf-8', timeout=180, check=False)
        try:
            conteudo = json.loads(resultado.stdout)
        except ValueError:
            conteudo = None
        provas.append({'comando': comando[1:], 'exit_code': resultado.returncode,
                       'resultado': conteudo, 'stderr': resultado.stderr})
    depois = sha(manifesto)
    reaberto = provas[0]['resultado'] or {}
    consulta = provas[1]['resultado'] or {}
    assinatura = ler(manifesto)['assinatura']
    sucesso = (all(p['exit_code'] == 0 for p in provas) and antes == depois
               and reaberto.get('reaberto_sem_ingestao') is True
               and reaberto.get('autoconsulta_confirmada') is True
               and consulta.get('assinatura_indice') == assinatura
               and any(t['chunk_id'] == 'c_f2c6f00293fae365' for t in consulta.get('trechos', [])))
    registro = {'executado_em': datetime.now(timezone.utc).isoformat(),
                'sem_ingestao': True, 'sem_gemini': True, 'modelos_em_modo_offline': True,
                'manifesto_sha_antes': antes, 'manifesto_sha_depois': depois,
                'processos_novos': provas, 'sucesso': sucesso}
    gravar(pasta / 'persistencia.json', registro)
    print(json.dumps({'sucesso': sucesso, 'arquivo': str(pasta / 'persistencia.json')}, ensure_ascii=False))


def calcular(args):
    pasta = Path(args.pasta).resolve()
    dados, gold, julgamentos = (ler(pasta / f'{n}.json') for n in ('execucoes', 'gabarito', 'julgamentos'))
    questoes = {q['id']: q for q in gold['perguntas']}
    execucoes = {q['id']: q for q in dados['execucoes']}
    julgados = {q['id']: q for q in julgamentos['perguntas']}
    if set(questoes) != set(execucoes) or set(questoes) != set(julgados):
        raise ValueError('Faltam execuções ou julgamentos')
    linhas = []
    for qid, q in questoes.items():
        e, j = execucoes[qid], julgados[qid]
        trechos = e.get('log_backend', {}).get('recuperacao', {}).get('trechos', [])
        ids = [t['chunk_id'] for t in trechos]
        if ids != [t['chunk_id'] for t in j['trechos']]:
            raise ValueError(f'{qid}: julgue todos os trechos, na ordem recuperada')
        claims = e.get('resposta', {}).get('claims', [])
        citacoes_esperadas = [(i, cid) for i, c in enumerate(claims) for cid in c['sourceIds']]
        if citacoes_esperadas != [(c['claim'], c['chunk_id']) for c in j['citacoes']]:
            raise ValueError(f'{qid}: julgue todos os vínculos de citação')
        for i in range(len(claims)):
            if not any(f['claim'] == i for f in j['fatos']):
                raise ValueError(f'{qid}: claim sem decomposição factual')
        linhas.append({'id': qid, 'respondivel': q['respondiveis'], 'tipo': q['tipo'],
                       'http_ok': e.get('http_status') == 200,
                       'relevantes': sum(t['relevante'] for t in j['trechos']), 'recuperados': len(ids),
                       'fatos_sustentados': sum(f['sustentado'] for f in j['fatos']), 'fatos': len(j['fatos']),
                       'citacoes_resolvidas': sum(c['resolvida'] for c in j['citacoes']), 'citacoes': len(j['citacoes']),
                       'ausencia_correta': j.get('ausencia_correta'), 'resposta_completa': j['resposta_completa'],
                       'premissa_corrigida': j.get('premissa_corrigida')})
    positivas = [l for l in linhas if l['respondivel']]
    negativas = [l for l in linhas if not l['respondivel']]
    metas = gold['metas_piloto']
    def soma(campo, itens=linhas):
        return sum(l[campo] for l in itens)
    persistencia = ler(pasta / 'persistencia.json')
    resultados = {
        'avaliador': julgamentos['avaliador'], 'execucao': pasta.name,
        'configuracao_preservada': dados['configuracao_preservada'],
        'hit_at_5': razao(sum(l['relevantes'] > 0 for l in positivas), len(positivas), metas['hit_at_5']),
        'precisao_todas': razao(soma('relevantes'), soma('recuperados'), metas['precisao_todas']),
        'precisao_respondiveis': razao(soma('relevantes', positivas), soma('recuperados', positivas), metas['precisao_respondiveis']),
        'fundamentacao': razao(soma('fatos_sustentados'), soma('fatos'), metas['fundamentacao']),
        'rastreabilidade': razao(soma('citacoes_resolvidas'), soma('citacoes'), metas['rastreabilidade']),
        'ausencia': razao(sum(l['ausencia_correta'] is True for l in negativas), len(negativas), metas['ausencia']),
        'persistencia': {'valor': int(persistencia['sucesso']), 'meta': 1, 'atingiu_meta': persistencia['sucesso']},
        'disponibilidade': razao(soma('http_ok'), len(linhas)),
        'cobertura_respostas_respondiveis': razao(sum(l['resposta_completa'] for l in positivas), len(positivas)),
        'premissas_corrigidas': razao(sum(l['premissa_corrigida'] is True for l in linhas if l['tipo'] == 'premissa_incorreta'),
                                     sum(l['tipo'] == 'premissa_incorreta' for l in linhas)),
        'por_pergunta': linhas}
    tentativas = dados.get('tentativas', dados['execucoes'])
    primeiras = [next(t for t in tentativas if t['id'] == qid) for qid in questoes]
    resultados['execucao_tecnica'] = {
        'total_chamadas': len(tentativas),
        'falhas': sum(t.get('http_status') != 200 for t in tentativas),
        'retentativas': len(tentativas) - len(questoes),
        'sucesso_primeira_tentativa': razao(sum(t.get('http_status') == 200 for t in primeiras), len(questoes)),
        'sucesso_por_chamada': razao(sum(t.get('http_status') == 200 for t in tentativas), len(tentativas)),
        'tentativas_por_pergunta': {qid: sum(t['id'] == qid for t in tentativas) for qid in questoes}}
    gravar(pasta / 'metricas.json', resultados)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest='comando', required=True)
    rodar = comandos.add_parser('executar', help='Chama Gemini real pela API já iniciada')
    rodar.add_argument('--endpoint', default='http://127.0.0.1:8001/api/v1/chat')
    rodar.add_argument('--max-tentativas', type=int, default=1)
    rodar.add_argument('--intervalo', type=float, default=3)
    rodar.add_argument('--retomar', help='Retoma somente falhas técnicas da mesma rodada e configuração')
    contas = comandos.add_parser('calcular', help='Agrega julgamentos já preenchidos, sem chamar API')
    contas.add_argument('pasta')
    conferir = comandos.add_parser('persistencia', help='Reabre o banco em processos novos, sem rede e sem ingestão')
    conferir.add_argument('pasta')
    argumentos = parser.parse_args()
    if argumentos.comando == 'executar' and (argumentos.max_tentativas < 1 or not 0 <= argumentos.intervalo <= 60):
        parser.error('Use pelo menos uma tentativa e intervalo entre 0 e 60 segundos')
    {'executar': executar, 'calcular': calcular, 'persistencia': conferir_persistencia}[argumentos.comando](argumentos)
