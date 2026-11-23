"""Contrato da grade importada: exemplos válidos e recusa de dados pessoais do aluno."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag.grade import RespostaGrade

EXEMPLOS = Path(__file__).parent / 'exemplos_grade'


def carregar(nome):
    return json.loads((EXEMPLOS / nome).read_text(encoding='utf-8'))


@pytest.mark.parametrize('nome', ['completo.json', 'parcial.json'])
def test_exemplos_validam(nome):
    RespostaGrade.model_validate(carregar(nome))


def test_parcial_nao_distribui_locais_pelos_encontros():
    turma = RespostaGrade.model_validate(carregar('parcial.json')).grade.turmas[0]
    assert len(turma.locaisDeclarados) == 2 and len(turma.encontros) == 2
    assert not hasattr(turma.encontros[0], 'local')
    assert turma.vinculoEncontrosLocais == 'nao_informado'


@pytest.mark.parametrize('campo', ['nome', 'matricula', 'numeroDocumento', 'codigoVerificacao'])
def test_recusa_dados_do_aluno(campo):
    dados = carregar('completo.json')
    dados['grade'][campo] = 'valor'
    with pytest.raises(ValidationError):
        RespostaGrade.model_validate(dados)


def test_dois_locais_sem_pendencia_e_recusado():
    dados = carregar('parcial.json')
    dados['grade']['turmas'][0]['pendencias'] = []
    with pytest.raises(ValidationError):
        RespostaGrade.model_validate(dados)
