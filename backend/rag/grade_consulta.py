"""Orquestra a consulta da grade (issue #16): leitura, vínculo com a base e resposta com fontes.

O comprovante e a imagem nunca chegam ao gerador: ele recebe apenas fatos estruturados já
extraídos (um trecho por turma, vindo do comprovante, e um por local, vindo da base). Nada é
gravado em `data/execucoes` nem indexado; a pergunta e o arquivo existem só em memória.
"""
from __future__ import annotations

import time

from rag.consulta.geracao import FalhaGeracao
from rag.grade import Citacao, GradeImportada, Pendencia, RespostaGrade, VinculoBase
from rag.grade_locais import Inventario, enriquecer_grade

ORIGEM_COMPROVANTE = 'COMPROVANTE'
TENTATIVAS_GERACAO = 8   # o Gemini devolve 502/503 passageiros em picos de demanda
ESPERA_GERACAO_S = 2.0
DIAS = {'seg': 'segunda-feira', 'ter': 'terça-feira', 'qua': 'quarta-feira',
        'qui': 'quinta-feira', 'sex': 'sexta-feira', 'sab': 'sábado'}
AVISOS = {
    'locais_sem_vinculo_com_encontros': 'O comprovante lista mais de um local para a turma sem informar qual deles é usado em cada encontro.',
    'local_a_definir': 'O local desta turma consta como "A definir" no comprovante.',
    'encontros_ausentes': 'Nenhum horário desta turma foi lido na grade semanal do comprovante.',
    'leitura_incerta': 'Parte desta linha do comprovante ficou ilegível e precisa de conferência.',
}


def _trecho_comprovante(grade: GradeImportada, turma) -> dict:
    partes = [f'{turma.codigoComponente}' + (f' - {turma.nomeComponente}' if turma.nomeComponente else '')
              + (f' ({turma.cargaHoraria}h)' if turma.cargaHoraria else '') + '.']
    if turma.turma:
        partes.append(f'{turma.turma}.')
    if turma.situacaoOriginal:
        partes.append(f'Situação no comprovante: {turma.situacaoOriginal}.')
    if turma.encontros:
        partes.append('Horários: ' + '; '.join(
            f'{DIAS[e.dia]} das {e.inicio} às {e.fim}' for e in turma.encontros) + '.')
    if turma.localTextoOriginal:
        partes.append(f'Local declarado no comprovante: {turma.localTextoOriginal}.')
    partes += [AVISOS[p.codigo] for p in turma.pendencias if p.codigo in AVISOS]
    return {'chunk_id': f'doc_{turma.codigoComponente}', 'source_id': ORIGEM_COMPROVANTE,
            'titulo': 'Comprovante de matrícula enviado', 'texto': ' '.join(partes), 'url': '',
            'secoes': ['Turmas selecionadas'], 'versao': grade.semestre or '', 'data_revisao': '',
            'validade': 'desconhecida'}


def _trechos_base(turma) -> list[dict]:
    trechos = []
    for i, loc in enumerate(turma.localizacoes):
        onde = f'prédio {loc.predio}' + (f', andar {loc.andar}' if loc.andar else '; o andar não é confirmado pela fonte')
        if loc.ambienteId:
            onde += f' (ambiente {loc.ambienteId})'
        texto = f'Local "{loc.textoOriginal}" do componente {turma.codigoComponente}: {onde}.'
        if loc.limitacoes:
            texto += f' Limitação da fonte: {loc.limitacoes}'
        trechos.append({'chunk_id': f'base_{turma.codigoComponente}_{i}', 'source_id': loc.fonte.identificador,
                        'titulo': loc.fonte.titulo, 'texto': texto, 'url': '', 'secoes': [loc.predio],
                        'versao': loc.fonte.versaoFonte, 'data_revisao': '', 'validade': 'desconhecida'})
    return trechos


def montar_trechos(grade: GradeImportada) -> list[dict]:
    trechos = []
    for turma in grade.turmas:
        trechos.append(_trecho_comprovante(grade, turma))
        trechos += _trechos_base(turma)
    return trechos


def _enriquecer(grade: GradeImportada, inventario: Inventario | None) -> GradeImportada:
    """Uma falha no vínculo preserva a grade lida e marca os locais como pendentes."""
    try:
        return enriquecer_grade(grade, inventario)
    except (ValueError, OSError, KeyError, TypeError):
        turmas = []
        for turma in grade.turmas:
            pendencias = list(turma.pendencias)
            if any(l.situacao != 'a_definir' for l in turma.locaisDeclarados):
                pendencias.append(Pendencia(
                    codigo='enriquecimento_indisponivel', codigoComponente=turma.codigoComponente,
                    mensagem='Não foi possível consultar a base do campus; prédio e andar do local ficaram pendentes.'))
            turmas.append(turma.model_copy(update={'pendencias': pendencias}))
        return GradeImportada.model_validate(grade.model_copy(update={'turmas': turmas}).model_dump())


def _citacoes(fontes_publicas: list[dict]) -> tuple[list[Citacao], list[VinculoBase]]:
    citacoes, vinculos = [], {}
    for n, fonte in enumerate(fontes_publicas, 1):
        doc = fonte['sourceId'] == ORIGEM_COMPROVANTE
        citacoes.append(Citacao(
            n=n, origem='comprovante' if doc else 'base',
            referencia=fonte['id'].removeprefix('doc_') if doc else fonte['sourceId'],
            trecho=fonte['excerpt'][:1500], versao=fonte['version'] or None))
        if not doc:
            vinculos.setdefault(fonte['sourceId'], VinculoBase(
                identificador=fonte['sourceId'], titulo=fonte['title'], versaoFonte=fonte['version'] or 'desconhecida'))
    return citacoes, list(vinculos.values())


def _gerar(gerador, pergunta: str, trechos: list[dict]) -> dict:
    """Repete falhas passageiras do Gemini (5xx, conexão e timeout); só a cota (429) não repete."""
    for tentativa in range(TENTATIVAS_GERACAO):
        try:
            return gerador.gerar(pergunta, trechos)
        except FalhaGeracao as erro:
            if erro.status not in (502, 503, 504) or tentativa == TENTATIVAS_GERACAO - 1:
                raise
            time.sleep(ESPERA_GERACAO_S)


def consultar_grade(conteudo: bytes, pergunta: str | None, leitor, gerador, inventario: Inventario | None = None) -> RespostaGrade:
    grade = _enriquecer(leitor.ler(conteudo), inventario)  # falhas de leitura sobem como FalhaGeracao
    pergunta = (pergunta or '').strip() or None
    if pergunta is None:
        return RespostaGrade(grade=grade, respostaStatus='sem_pergunta')
    if not grade.turmas:
        return RespostaGrade(grade=grade, pergunta=pergunta, respostaStatus='insuficiente',
                             resposta='Não encontrei turmas no arquivo enviado para responder.')
    try:
        resultado = _gerar(gerador, pergunta, montar_trechos(grade))
    except FalhaGeracao:
        return RespostaGrade(grade=grade, pergunta=pergunta, respostaStatus='indisponivel')
    if resultado['status'] != 'answered':
        return RespostaGrade(grade=grade, pergunta=pergunta, respostaStatus='insuficiente',
                             resposta=resultado['message'])
    citacoes, fontes = _citacoes(resultado['sources'])
    return RespostaGrade(grade=grade, pergunta=pergunta, respostaStatus='respondida',
                         resposta=resultado['answer'], citacoes=citacoes, fontes=fontes)
