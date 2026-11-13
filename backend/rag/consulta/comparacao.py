"""Comparação observável: RAG atual e o mesmo Gemini sem documentos ou histórico."""
import hashlib
import csv
import json
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from rag.config import caminho_projeto
from rag.consulta.geracao import FalhaGeracao, PROMPT
from rag.consulta.llm_isolada import livre, PROMPT_LIVRE
from rag.armazenamento.manifesto import gravar_json

RODADA = 'semana3-llm-rag-20261112-v1'


def rastrear(resposta, config):
    """Verifica a cadeia documental; não julga se uma citação sustenta o fato."""
    pares = [cid for c in resposta.get('claims', []) for cid in c.get('sourceIds', [])]
    if not pares:
        return {'resolved': 0, 'total': 0, 'value': None, 'reason': 'Nenhum vínculo de citação.'}
    caminhos = config['caminhos']
    chunks = {c['chunk_id']: c for c in (json.loads(l) for l in
              caminho_projeto(caminhos['chunks']).read_text(encoding='utf-8').splitlines() if l.strip())}
    with caminho_projeto(caminhos['catalogo']).open(encoding='utf-8-sig') as f:
        catalogo = {c['source_id']: c for c in csv.DictReader(f)}
    recuperados = {t['id']: t for t in resposta.get('retrieved', [])}
    resolvidas = 0
    for cid in pares:
        c = chunks.get(cid)
        if not c:
            continue
        fonte = catalogo[c['source_id']]
        originais = list((caminho_projeto(caminhos['originais']) / c['source_id'] / c['versao']).glob('original.*'))
        extraido = caminho_projeto(caminhos['extraido']) / f'{c["source_id"]}__{c["versao"]}.json'
        if not originais or not extraido.is_file():
            return {'resolved': None, 'total': len(pares), 'value': None,
                    'reason': 'Originais ou extrações ausentes neste deploy; cadeia completa não verificada.'}
        extr = json.loads(extraido.read_text(encoding='utf-8'))
        t = recuperados.get(cid, {})
        ok = (c['versao'] == fonte['versao'] == t.get('version')
              and c['sha256_original'] == fonte['sha256'] == extr['sha256_original']
              and hashlib.sha256(originais[0].read_bytes()).hexdigest() == fonte['sha256']
              and t.get('excerpt') == c['texto'] and t.get('url') == c['url']
              and t.get('section') == ' > '.join(c['secoes']) and t.get('sourceId') == c['source_id'])
        resolvidas += bool(ok)
    return {'resolved': resolvidas, 'total': len(pares), 'value': resolvidas / len(pares),
            'reason': 'IDs, texto, documento, versão, seção, URL e hash do original conferidos.'}


def painel_historico(info=None):
    pasta = caminho_projeto(f'avaliacao/resultados/{RODADA}')
    arquivos = {nome: pasta / f'{nome}.json' for nome in ('metricas', 'gabarito', 'configuracao')}
    dados = {nome: json.loads(path.read_text(encoding='utf-8')) for nome, path in arquivos.items()}
    metricas, gold = dados['metricas'], dados['gabarito']
    cfg = dados['configuracao']
    persistencia = metricas['persistencia']
    processos = persistencia.get('processos_novos', [])
    assinatura = next((p['resultado']['assinatura_indice'] for p in processos
                       if 'assinatura_indice' in p.get('resultado', {})), None)
    return {
        'round': RODADA, 'date': '2026-11-12', 'reviewer': metricas['avaliador'],
        'model': cfg['config']['geracao']['modelo'], 'baseVersion': assinatura,
        'currentBaseMatches': info.get('baseVersion') == assinatura if info and assinatura else None,
        'arms': metricas['bracos'], 'scenarios': metricas['testes'],
        'questions': gold['perguntas'], 'judgments': metricas['perguntas'],
        'goals': gold['metas_piloto'], 'rubric': gold['rubrica'],
        'persistence': {'success': bool(processos) and all(p['exit_code'] == 0 for p in processos)
                        and persistencia.get('sem_ingestao') is True
                        and persistencia['manifesto_sha_antes'] == persistencia['manifesto_sha_depois'],
                        'executedAt': persistencia['executado_em']},
        'artifacts': [{'path': f'backend/avaliacao/resultados/{RODADA}/{p.name}',
                       'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in arquivos.values()],
    }


class Comparador:
    def __init__(self, servico):
        self.servico = servico
        self.vaga_llm = threading.BoundedSemaphore(1)

    def executar(self, braco, texto):
        inicio = time.perf_counter()
        registro = {'id': str(uuid4()), 'arm': braco, 'question': texto,
                    'executedAt': datetime.now(timezone.utc).isoformat(),
                    'model': self.servico.info['model'], 'baseVersion': self.servico.info['baseVersion'],
                    'generation': self.servico.config['geracao'],
                    'promptSha256': hashlib.sha256((PROMPT if braco == 'rag' else PROMPT_LIVRE).encode()).hexdigest()}
        try:
            if braco == 'rag':
                resposta = self.servico.perguntar(texto)  # Sem histórico nos dois braços.
            else:
                gerador = self.servico.gerador
                if not gerador.chave:
                    raise FalhaGeracao('Configure GEMINI_API_KEY no backend.', 503)
                if not self.vaga_llm.acquire(blocking=False):
                    raise FalhaGeracao('Já há uma comparação Gemini em andamento.', 429)
                try:
                    with httpx.Client(timeout=gerador.config['timeout_s']) as cliente:
                        saida = livre(cliente, gerador.chave, gerador.config, texto)
                    if saida['status_tecnico'] != 200:
                        raise FalhaGeracao(saida['erro'], saida['status_tecnico'])
                    resposta = saida['resposta']
                finally:
                    self.vaga_llm.release()
            registro.update(technicalStatus=200, response=resposta)
            if braco == 'rag':
                try:
                    registro['traceability'] = rastrear(resposta, self.servico.config)
                except (OSError, ValueError, KeyError):
                    registro['traceability'] = {'value': None, 'reason': 'Não foi possível conferir a cadeia documental.'}
            else:
                total = sum(len(c.get('fontes', [])) for c in resposta.get('claims', []))
                registro['traceability'] = {'resolved': 0, 'total': total, 'value': 0 if total else None,
                    'reason': 'URLs avulsas não incluem documento e versão preservados; isso não mede se a URL está ativa.'}
        except FalhaGeracao as erro:
            registro.update(technicalStatus=erro.status, error=str(erro))
        except (ValueError, OSError, KeyError, TypeError):
            registro.update(technicalStatus=503, error='Não foi possível concluir a comparação. Confira o backend.')
        registro['elapsedSeconds'] = round(time.perf_counter() - inicio, 4)
        # Cada tentativa fica preservada; um erro não é uma abstenção correta.
        gravar_json(caminho_projeto(self.servico.config['caminhos']['execucoes']) /
                    f'comparacao-{registro["id"]}.json', registro)
        return registro
