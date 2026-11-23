"""Vínculo dos locais da grade com o inventário real do Grupo 09 e com casos sintéticos."""
import pytest

from rag.grade import GradeImportada, LocalDeclarado, Turma, VinculoBase
from rag.grade_locais import Ambiente, Inventario, Trecho, enriquecer_grade


def grade_com(*locais, texto_original=None):
    declarados = [l if isinstance(l, LocalDeclarado) else LocalDeclarado(textoOriginal=l, codigo=l) for l in locais]
    pendencias = []
    if any(l.situacao == 'a_definir' for l in declarados):
        pendencias = [{'codigo': 'local_a_definir', 'mensagem': 'x', 'codigoComponente': 'FGA9001'}]
    return GradeImportada.model_validate({
        'origem': 'imagem', 'semestre': '2099.1',
        'turmas': [Turma(codigoComponente='FGA9001', turma='Turma 01', localTextoOriginal=texto_original,
                         locaisDeclarados=declarados, pendencias=pendencias).model_dump()]})


def codigos(turma):
    return [p.codigo for p in turma.pendencias]


def test_i2_e_s10_ficam_no_uac_com_a_fonte_do_mapa():
    t1 = enriquecer_grade(grade_com('I2')).turmas[0]
    t2 = enriquecer_grade(grade_com('S10')).turmas[0]
    i2, s10 = t1.localizacoes[0], t2.localizacoes[0]
    assert (i2.predio, i2.andar, i2.ambienteId, i2.evidencia, i2.precisao) == ('UAC', 'Térreo', 'T-001', 'mapa', 'ambiente')
    assert i2.fonte.identificador == 'MAP-UAC-0' and i2.fonte.versaoFonte
    assert (s10.predio, s10.andar, s10.ambienteId) == ('UAC', 'Superior', 'S-029')
    assert s10.fonte.identificador == 'MAP-UAC-1'


def test_mocap_confirma_so_o_predio_e_deixa_o_andar_em_aberto():
    loc = enriquecer_grade(grade_com('MOCAP')).turmas[0].localizacoes[0]
    assert (loc.predio, loc.andar, loc.ambienteId, loc.evidencia, loc.precisao) == ('UED', None, None, 'texto', 'predio')
    assert loc.fonte.identificador == 'DOC-006'


def test_s10_e_mocap_mantem_os_dois_locais_e_o_texto_original():
    grade = grade_com('S10', 'MOCAP', texto_original='FCTE - S10 / MOCAP')
    turma = enriquecer_grade(grade).turmas[0]
    assert [l.textoOriginal for l in turma.locaisDeclarados] == ['S10', 'MOCAP']
    assert [l.textoOriginal for l in turma.localizacoes] == ['S10', 'MOCAP']
    assert turma.localTextoOriginal == 'FCTE - S10 / MOCAP'


@pytest.mark.parametrize('codigo', ['XYZ99', 'S99', 'LCA'])
def test_codigo_desconhecido_vira_pendencia_sem_inventar_local(codigo):
    turma = enriquecer_grade(grade_com(codigo)).turmas[0]
    assert turma.localizacoes == [] and 'local_nao_encontrado_na_base' in codigos(turma)


def test_a_definir_nao_recebe_localizacao():
    turma = enriquecer_grade(grade_com(LocalDeclarado(textoOriginal='A definir', situacao='a_definir'))).turmas[0]
    assert turma.localizacoes == [] and codigos(turma) == ['local_a_definir']


def fonte(sid):
    return VinculoBase(identificador=sid, titulo='Fonte de exemplo', versaoFonte='v1')


def ambiente(id_, nome, predio):
    return Ambiente(id=id_, nome=nome, predio=predio, andar='Térreo', nivel=0, fonte=fonte('MAP-X'), limitacoes=None)


def test_mesmo_nome_em_dois_ambientes_e_ambiguo():
    inv = Inventario([ambiente('T-1', 'Sala 1', 'UAC'), ambiente('T-9', 'Sala 1', 'UED')], [])
    turma = enriquecer_grade(grade_com('Sala 1'), inv).turmas[0]
    assert turma.localizacoes == [] and 'local_ambiguo_na_base' in codigos(turma)


def test_texto_que_cita_dois_predios_na_mesma_frase_nao_decide():
    inv = Inventario([], [Trecho('O laboratorio ZETA funciona na UAC e na UED.', fonte('DOC-X'))])
    turma = enriquecer_grade(grade_com('ZETA'), inv).turmas[0]
    assert turma.localizacoes == [] and 'local_nao_encontrado_na_base' in codigos(turma)


def test_predios_diferentes_em_trechos_diferentes_e_ambiguo():
    inv = Inventario([], [Trecho('O laboratorio ZETA fica na UAC.', fonte('DOC-X')),
                          Trecho('O laboratorio ZETA fica na UED.', fonte('DOC-Y'))])
    turma = enriquecer_grade(grade_com('ZETA'), inv).turmas[0]
    assert turma.localizacoes == [] and 'local_ambiguo_na_base' in codigos(turma)
