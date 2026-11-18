"""Prepara planilha de julgamentos e resume resultados dos tres modos.

1. python backend/scripts/resumir_tres_modos.py PASTA --preparar
2. Preencher julgamentos.json com revisao humana baseada nas fontes originais.
3. python backend/scripts/resumir_tres_modos.py PASTA

Numeradores e denominadores sao explicitos; campos sem revisao permanecem N/A.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

BRACOS = ('llm','rag','multiagente')
USAGE = ('promptTokenCount','candidatesTokenCount','thoughtsTokenCount','totalTokenCount')


def ler(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def salvar(p, dados):
    Path(p).write_text(json.dumps(dados, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


def razao(n,d):
    return {'numerador':n,'denominador':d,'valor':n/d if d else None}


def template(pasta):
    dados=ler(pasta/'execucoes.json')
    gold={q['id']:q for q in ler(pasta/'gabarito.json')['perguntas']}
    revisoes=[]
    for e in dados['selecionadas']:
        resp=e.get('response') or {}
        trechos=resp.get('retrieved') or []
        pares=[{'claim':i,'chunk_id':cid,'sustenta_claim':None,'rastreavel':None}
               for i,claim in enumerate(resp.get('claims') or []) for cid in claim.get('sourceIds') or []]
        revisoes.append({
            'qid':e['qid'],'braco':e['braco'],'attemptId':e['id'],
            'revisor':'','observacao':'','completa':None,'ausencia_correta':None,
            'premissa_corrigida':None,
            'fatos':[{'text':c.get('text'),'corroborado':None,'fundamentado':None}
                     for c in resp.get('claims') or []],
            'trechos':[{'chunk_id':t['id'],'relevante':None} for t in trechos] if e['braco']!='llm' else [],
            'citacoes':pares if e['braco']!='llm' else [],
            'correcao':None,  # melhorou | piorou | neutra | sem_correcao
            'fonte_consultada':'', 'gabarito':gold[e['qid']]['referencia']})
    path=pasta/'julgamentos.json'
    if path.exists():
        raise ValueError('Julgamentos ja existem; nao sobrescrever revisao humana!')
    salvar(path,{'metodologia':'Revisao humana; sem juiz LLM; verificar fontes originais e claims atomicas.',
                 'revisoes':revisoes})
    print(f'Template criado: {path}. Preencha campos e fontes antes de calcular.')


def resultado_braco(nome, dados, avaliacoes, gold):
    tentativas=[t for t in dados['tentativas'] if t['braco']==nome]
    selecionadas=[t for t in dados['selecionadas'] if t['braco']==nome]
    analisadas={(r['qid'],r['braco']):r for r in avaliacoes if r['braco']==nome}
    metricas={}
    def medir(key, candidatos, cond, ok):
        denom=[r for r in candidatos if cond(r)]
        return razao(sum(bool(ok(r)) for r in denom),len(denom))
    revisoes=[analisadas[(e['qid'],nome)] for e in selecionadas
              if (e['qid'],nome) in analisadas and
              all(analisadas[(e['qid'],nome)].get(f) for f in ('revisor','observacao','fonte_consultada'))]
    completas=[r for r in revisoes if r['completa'] is not None and gold[r['qid']]['respondiveis']]
    ausencias=[r for r in revisoes if r['ausencia_correta'] is not None and not gold[r['qid']]['respondiveis']]
    premissas=[r for r in revisoes if r['premissa_corrigida'] is not None and gold[r['qid']]['tipo']=='premissa_incorreta']
    metricas['completude']=razao(sum(r['completa'] is True for r in completas),len(completas))
    metricas['ausencia']=razao(sum(r['ausencia_correta'] is True for r in ausencias),len(ausencias))
    metricas['premissas']=razao(sum(r['premissa_corrigida'] is True for r in premissas),len(premissas))
    fatos=[f for r in revisoes for f in r['fatos'] if f['corroborado'] is not None]
    metricas['corroboracao']=razao(sum(f['corroborado'] is True for f in fatos),len(fatos))
    metricas['fundamentacao'] = None
    metricas['hit_at_5'] = None
    metricas['precisao_trechos'] = None
    metricas['mrr_at_5'] = None
    metricas['rastreabilidade'] = None
    metricas['adequacao_citacoes'] = None
    if nome!='llm':
        todos=[t for r in revisoes for t in r['trechos'] if t['relevante'] is not None]
        respondiveis=[r for r in revisoes if gold[r['qid']]['respondiveis'] and
                      all(t['relevante'] is not None for t in r['trechos'])]
        metricas['hit_at_5']=razao(sum(any(t['relevante'] for t in r['trechos'][:5]) for r in respondiveis),len(respondiveis))
        metricas['precisao_trechos']=razao(sum(t['relevante'] is True for t in todos),len(todos))
        mrr=[next((1/i for i,t in enumerate(r['trechos'][:5],1) if t['relevante']),0) for r in respondiveis]
        metricas['mrr_at_5']=statistics.mean(mrr) if mrr else None
        fundamentados=[f for r in revisoes for f in r['fatos'] if f['fundamentado'] is not None]
        metricas['fundamentacao']=razao(sum(f['fundamentado'] is True for f in fundamentados),len(fundamentados))
        citacoes=[c for r in revisoes for c in r['citacoes']]
        rastro=[c for c in citacoes if c['rastreavel'] is not None]
        adequacao=[c for c in citacoes if c['sustenta_claim'] is not None]
        metricas['rastreabilidade']=razao(sum(c['rastreavel'] is True for c in rastro),len(rastro))
        metricas['adequacao_citacoes']=razao(sum(c['sustenta_claim'] is True for c in adequacao),len(adequacao))
    metricas['saidas_validas']=len(selecionadas)
    metricas['perguntas_planejadas']=len(gold)
    metricas['tentativas']=len(tentativas)
    metricas['falhas_tecnicas']=sum(t.get('technicalStatus')!=200 for t in tentativas)
    metricas['sucesso_por_tentativa']=razao(sum(t.get('technicalStatus')==200 for t in tentativas),len(tentativas))
    iniciadas=set(t['qid'] for t in tentativas)
    metricas['sucesso_primeira_tentativa']=razao(sum(any(t['qid']==qid and t['tentativa']==1 and t['technicalStatus']==200 for t in tentativas) for qid in iniciadas),len(iniciadas))
    tempos=[t['elapsedSeconds'] for t in selecionadas if t.get('elapsedSeconds') is not None]
    metricas['latencia_valida_s']={'media':statistics.mean(tempos) if tempos else None,
                                    'mediana':statistics.median(tempos) if tempos else None,
                                    'amostra':len(tempos)}
    tempos_todos=[t['elapsedSeconds'] for t in tentativas if t.get('elapsedSeconds') is not None]
    metricas['esforco_total_s']=sum(tempos_todos)
    metricas['tempos_incompletos']=len(tempos_todos)!=len(tentativas)
    usage=[t['response']['usage'] for t in selecionadas if t.get('response',{}).get('usage')]
    usage_completo=sum(
        (t['response'].get('usageCoverage',{}).get('callsWithUsage') ==
         t['response'].get('usageCoverage',{}).get('calls'))
        if nome == 'multiagente' else bool(t.get('response',{}).get('usage'))
        for t in selecionadas)
    metricas['tokens_validos']={k:sum(int(u.get(k,0)) for u in usage) for k in USAGE}
    metricas['usage_registrado']=razao(usage_completo,len(selecionadas))
    metricas['tokens_validos_podem_ser_parciais']=usage_completo < len(selecionadas)
    if nome=='multiagente':
        metricas['chamadas_gemini']=sum(t.get('response',{}).get('llmCalls',0) for t in selecionadas)
        metricas['rodadas_correcao']=sum(t.get('response',{}).get('correctionRounds',0) for t in selecionadas)
        metricas['efeito_correcao']={k:sum(r['correcao']==k for r in revisoes)
                                    for k in ('melhorou','piorou','neutra','sem_correcao')}
    metricas['revisoes_identificadas']=len(revisoes)
    return metricas


def resumir(pasta):
    dados=ler(pasta/'execucoes.json')
    gold={q['id']:q for q in ler(pasta/'gabarito.json')['perguntas']}
    manual=ler(pasta/'julgamentos.json')['revisoes']
    validas={(s['qid'],s['braco']):s for s in dados['selecionadas']}
    for r in manual:
        k=(r['qid'],r['braco'])
        if k not in validas or r['attemptId']!=validas[k]['id']:
            raise ValueError(f'Revisao refere-se a outra tentativa ou pergunta: {k}')
        e=validas[k]
        if r['braco']!='llm':
            esperado=[t['id'] for t in e.get('response',{}).get('retrieved',[])]
            recebido=[t['chunk_id'] for t in r['trechos']]
            if esperado!=recebido:
                raise ValueError(f'Trechos recuperados divergentes: {k}')
            citados=[(i,cid) for i,c in enumerate(e.get('response',{}).get('claims',[]))
                     for cid in c.get('sourceIds',[])]
            if citados != [(c['claim'],c['chunk_id']) for c in r['citacoes']]:
                raise ValueError(f'Citacoes divergentes: {k}')
    saida={'conjunto':dados['conjunto'],'inicio':dados['inicio'],
           'concluida':dados.get('concluidas')==dados.get('esperadas'),
           'configuracao_preservada':dados.get('configuracao_preservada'),
           'criterio':'Numeradores/denominadores somente dos itens julgados; nao preenchidos nao viram zeros.',
           'bracos':{b:resultado_braco(b,dados,manual,gold) for b in BRACOS}}
    salvar(pasta/'metricas.json',saida)
    print(json.dumps(saida,ensure_ascii=False,indent=2))
    if any(not r.get('revisor') or not r.get('observacao') or not r.get('fonte_consultada') for r in manual):
        print('ATENCAO: avaliacao humana incompleta; nao publicar resultados como finais.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pasta',type=Path)
    p.add_argument('--preparar',action='store_true')
    a=p.parse_args()
    template(a.pasta.resolve()) if a.preparar else resumir(a.pasta.resolve())
