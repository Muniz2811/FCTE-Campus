"""Agrega a comparação pareada a partir de julgamentos explícitos, sem chamar LLM."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]


def ler(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def razao(n, d):
    return {'numerador': n, 'denominador': d, 'valor': n/d if d else None}


def percentil(valores, p):
    valores = sorted(valores)
    x = (len(valores)-1)*p
    i = int(x)
    return valores[i]+(valores[min(i+1,len(valores)-1)]-valores[i])*(x-i)


def resumo_linhas(linhas, julgamentos, tentativas, gold, braco):
    qs = {q['id']:q for q in gold['perguntas']}
    ids = {e['qid'] for e in linhas}
    positivas = [q for q in qs.values() if q['id'] in ids and q['respondiveis']]
    negativas = [q for q in qs.values() if q['id'] in ids and not q['respondiveis']]
    js = [j for j in julgamentos if j['braco']==braco and j['qid'] in ids]
    fatos = [f for j in js for f in j['fatos']]
    ts = [t for t in tentativas if t['braco']==braco and t['qid'] in ids]
    duracoes = [e['segundos'] for e in linhas]
    usos = [e['resposta'].get('usage',{}) for e in linhas]
    resultado = {
        'tarefas': len(linhas),
        'completude': razao(sum(j['completa'] for j in js if qs[j['qid']]['respondiveis']),len(positivas)),
        'corroboracao': razao(sum(f['corroborado'] for f in fatos),len(fatos)),
        'fatos_contraditos': sum(f['classificacao']=='contradito' for f in fatos),
        'fatos_nao_corroborados': sum(f['classificacao']=='nao_corroborado' for f in fatos),
        'ausencia': razao(sum(j.get('ausencia_correta') is True for j in js if not qs[j['qid']]['respondiveis']),len(negativas)),
        'premissas': razao(sum(j.get('premissa_corrigida') is True for j in js),sum(qs[qid]['tipo']=='premissa_incorreta' for qid in ids)),
        'latencia_valida_s': {'media':mean(duracoes),'mediana':median(duracoes),'p95':percentil(duracoes,.95)},
        'tentativas':len(ts),'falhas_tecnicas':sum(t['status_tecnico']!=200 for t in ts),
        'sucesso_primeira_tentativa':razao(sum(e['tentativa']==1 for e in linhas),len(linhas)),
        'sucesso_por_tentativa':razao(sum(t['status_tecnico']==200 for t in ts),len(ts)),
        'soma_duracoes_tentativas_s':sum(t['segundos'] for t in ts),
        'esforco_medio_tarefa_s':sum(t['segundos'] for t in ts)/len(linhas),
        'tokens_saidas_validas':{campo:sum(u.get(campo,0) for u in usos) for campo in ('promptTokenCount','candidatesTokenCount','thoughtsTokenCount','totalTokenCount')},
        'saidas_validas_com_usage':sum(bool(u) for u in usos),
    }
    if braco=='rag':
        trechos=[t for j in js for t in j['trechos']]
        pos=[j for j in js if qs[j['qid']]['respondiveis']]
        resultado['hit_at_5']=razao(sum(any(t['relevante'] for t in j['trechos']) for j in pos),len(positivas))
        resultado['precisao_trechos']=razao(sum(t['relevante'] for t in trechos),len(trechos))
        trechos_pos=[t for j in pos for t in j['trechos']]
        resultado['precisao_respondiveis']=razao(sum(t['relevante'] for t in trechos_pos),len(trechos_pos))
        reciprocais=[next((1/i for i,t in enumerate(j['trechos'],1) if t['relevante']),0) for j in pos]
        resultado['mrr_at_5']=mean(reciprocais) if reciprocais else None
        resultado['fundamentacao']=razao(sum(f.get('fundamentado') is True for f in fatos),len(fatos))
        cites=[c for j in js for c in j['citacoes']]
        resultado['rastreabilidade']=razao(sum(c['resolvida'] for c in cites),len(cites))
        resultado['adequacao_citacoes']=razao(sum(c['sustenta_claim'] for c in cites),len(cites))
    else:
        cites=[c for j in js for c in j['citacoes']]
        resultado['rastreabilidade']=razao(sum(c['resolvida'] for c in cites),len(cites))
    return resultado


def calcular(pasta):
    dados=ler(pasta/'execucoes.json');gold=ler(pasta/'gabarito.json');manual=ler(pasta/'julgamentos.json')
    linhas=dados['selecionadas'];js=manual['perguntas'];qids={q['id'] for q in gold['perguntas']}
    esperadas={(q,b) for q in qids for b in ('llm','rag')}
    assert {(e['qid'],e['braco']) for e in linhas}==esperadas,'Execuções incompletas'
    assert {(j['qid'],j['braco']) for j in js}==esperadas,'Julgamentos incompletos'
    chunks={c['chunk_id']:c for c in [json.loads(l) for l in (ROOT/'data/chunks/chunks.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]}
    with (ROOT/'data/catalogo/fontes.csv').open(encoding='utf-8-sig') as f:
        catalogo={c['source_id']:c for c in csv.DictReader(f)}
    for e in linhas:
        j=next(j for j in js if j['qid']==e['qid'] and j['braco']==e['braco'])
        validas=[t for t in dados['tentativas'] if t['qid']==e['qid'] and t['braco']==e['braco'] and t['status_tecnico']==200]
        assert validas[0]['tentativa']==e['tentativa'],'A seleção deve usar a primeira saída válida'
        claims=e['resposta'].get('claims',[])
        if e['braco']=='rag':
            recuperados=e['log_backend']['recuperacao']['trechos']
            assert [t['chunk_id'] for t in j['trechos']]==[t['chunk_id'] for t in recuperados]
            pares=[(i,cid) for i,c in enumerate(claims) for cid in c['sourceIds']]
            assert pares==[(c['claim'],c['chunk_id']) for c in j['citacoes']]
            for c in j['citacoes']:
                chunk=chunks[c['chunk_id']];fonte=catalogo[chunk['source_id']]
                original=list((ROOT/'data/originais'/chunk['source_id']/chunk['versao']).glob('original.*'))
                extr=ler(ROOT/'data/extraido'/f'{chunk["source_id"]}__{chunk["versao"]}.json')
                ok=(chunk['versao']==fonte['versao'] and chunk['sha256_original']==fonte['sha256']==extr['sha256_original']
                    and original and hashlib.sha256(original[0].read_bytes()).hexdigest()==fonte['sha256']
                    and any(t['chunk_id']==c['chunk_id'] and t['texto']==chunk['texto'] for t in recuperados))
                c['resolvida']=bool(ok)
        for i in range(len(claims)):
            assert any(f['claim']==i for f in j['fatos']),f'{e["qid"]}/{e["braco"]}: claim sem julgamento factual'
    resultado={'avaliador':manual['avaliador'],'configuracao_preservada':dados.get('configuracao_preservada'),
               'bracos':{},'testes':{},'perguntas':js}
    for b in ('llm','rag'):
        resultado['bracos'][b]=resumo_linhas([e for e in linhas if e['braco']==b],js,dados['tentativas'],gold,b)
    for t in ('T1','T2','T3','T4'):
        resultado['testes'][t]={b:resumo_linhas([e for e in linhas if e['braco']==b and e['teste']==t],js,dados['tentativas'],gold,b) for b in ('llm','rag')}
    resultado['persistencia']=ler(pasta/'persistencia.json')
    (pasta/'julgamentos.json').write_text(json.dumps(manual,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (pasta/'metricas.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in resultado.items() if k!='perguntas'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pasta');args=parser.parse_args()
    calcular(Path(args.pasta).resolve())
