"""Contexto curto por referência a log próprio. Histórico nunca é evidência factual."""
import json
import re
from pathlib import Path
from uuid import UUID

from rag.ingestao.normalizacao import marcar

COMPLEMENTO = re.compile(r'^(e\b|tamb[eé]m\b|l[aá]\b|nisso\b|nes[st][ea]\b|isso\b|elas?\b|eles?\b|'
                         r'tem\b|h[aá]\b|qual (?:o |é o )?hor[aá]rio\b|quanto\b)', re.IGNORECASE)


def contexto_da_consulta(pergunta, request_id, pasta: Path, base, entidades):
    if not request_id or not COMPLEMENTO.search(pergunta.strip()):
        return None
    try:
        identificador = str(UUID(str(request_id)))
        anterior = json.loads((pasta / f'chat-{identificador}.json').read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None
    resposta = anterior.get('resposta', {})
    if resposta.get('baseVersion') != base or resposta.get('status') != 'answered':
        return None
    # Um novo local nomeado tem prioridade sobre o tema anterior.
    atuais = set(marcar(pergunta, entidades))
    fontes = resposta.get('sources', [])
    assunto = anterior.get('pergunta', '') + '\n' + '\n'.join(f['title'] for f in fontes)
    anteriores = set(marcar(assunto, entidades))
    if atuais and not atuais.intersection(anteriores):
        return None
    titulos = list(dict.fromkeys(f['title'] for f in fontes))[:2]
    if not titulos:
        return None
    return {'requestId': identificador, 'pergunta': anterior['pergunta'], 'assunto': ' / '.join(titulos)}


def consulta_contextualizada(pergunta, contexto):
    # Título curto, sem rótulos "pergunta anterior/atual", que pioraram o E5 no diagnóstico.
    return pergunta if contexto is None else f"{contexto['assunto']}. {pergunta}"
