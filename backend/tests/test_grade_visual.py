"""Leitor visual da grade com Gemini falso e imagens sintéticas; sem rede, chave ou dados reais."""
import base64
import io
import json

import fitz
import httpx
import pytest
from PIL import Image

from rag.consulta.geracao import FalhaGeracao
from rag.grade_visual import LeitorVisual
from rag.grade_consulta import consultar_grade, montar_trechos
from rag.consulta.geracao import resolver_resposta

CONFIG = {'modelo': 'gemini-exemplo', 'timeout_s': 10}
LEITURA = {
    'semestre': '2099.1',
    'turmas': [
        {'codigo': 'FGA9001', 'nome': 'COMPONENTE UM', 'carga_horaria': 60, 'turma': 'Turma 01',
         'local': 'FCTE - S2', 'situacao': 'AGUARDANDO PROCESSAMENTO'},
        {'codigo': 'FGA9002', 'nome': 'COMPONENTE DOIS', 'carga_horaria': 60, 'turma': 'Turma 01',
         'local': 'FCTE - S10 / MOCAP', 'situacao': 'AGUARDANDO PROCESSAMENTO'},
        {'codigo': 'FGA9003', 'nome': 'COMPONENTE TRES', 'carga_horaria': 60, 'turma': 'Turma 01',
         'local': 'A definir', 'situacao': 'AGUARDANDO PROCESSAMENTO'}],
    'celulas': [
        {'dia': 'seg', 'inicio': '14:00', 'fim': '14:55', 'codigo': 'FGA9001'},
        {'dia': 'seg', 'inicio': '14:55', 'fim': '15:50', 'codigo': 'FGA9001'},
        {'dia': 'ter', 'inicio': '14:00', 'fim': '14:55', 'codigo': 'FGA9002'},
        {'dia': 'ter', 'inicio': '14:55', 'fim': '15:50', 'codigo': 'FGA9002'},
        {'dia': 'qua', 'inicio': '18:00', 'fim': '18:55', 'codigo': 'FGA9003'},
        {'dia': 'qua', 'inicio': '19:00', 'fim': '19:50', 'codigo': 'FGA9003'}]}


def imagem_sintetica(*, turmas=True, grade=True, periodo=True):
    with fitz.open() as doc:
        pagina = doc.new_page(width=620, height=380)
        pagina.draw_rect(fitz.Rect(0, 0, 620, 50), fill=(1, 0, 0))
        pagina.insert_text((20, 30), 'Discente: EXEMPLO FICTICIO')
        if periodo:
            pagina.insert_text((20, 75), 'Periodo 2099.1')
        if turmas:
            pagina.insert_text((20, 115), 'Codigo     Componente curricular          Turma          Local          Situacao')
            pagina.insert_text((20, 140), 'FGA9001    COMPONENTE UM                01             S2              Ativo')
        if grade:
            pagina.insert_text((20, 230), 'Horarios          Seg          Ter          Qua          Qui          Sex          Sab')
            pagina.insert_text((20, 255), '14:00 - 14:55    FGA9001')
        return pagina.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes('png')


def pdf_sem_texto(png):
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_image(pagina.rect, stream=png)
    assert pagina.get_text().strip() == ''
    return doc.tobytes()


def leitor(leitura=LEITURA):
    chamadas = []

    def handler(request):
        corpo = json.loads(request.content)
        imagens = [base64.b64decode(p['inlineData']['data']) for p in corpo['contents'][0]['parts']]
        prompt = corpo['systemInstruction']['parts'][0]['text']
        chamadas.append({'prompt': prompt, 'imagens': imagens})
        dados = leitura
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(dados)}]}}]})
    return LeitorVisual(CONFIG, 'chave-falsa', transport=httpx.MockTransport(handler)), chamadas


def codigos(pendencias):
    return [p.codigo for p in pendencias]


def test_print_completo_funde_horarios_e_preserva_locais_sem_vinculo():
    ler, _ = leitor()
    grade = ler.ler(imagem_sintetica())
    assert grade.origem == 'imagem' and grade.semestre == '2099.1'
    assert grade.pendencias == []  # aguardando processamento e locais múltiplos são avisos por turma
    t1, t2, t3 = grade.turmas
    assert [(e.dia, e.inicio, e.fim) for e in t1.encontros] == [('seg', '14:00', '15:50')]
    assert [(e.dia, e.inicio, e.fim) for e in t3.encontros] == [('qua', '18:00', '19:50')]
    assert [loc.codigo for loc in t2.locaisDeclarados] == ['S10', 'MOCAP']
    assert 'locais_sem_vinculo_com_encontros' in codigos(t2.pendencias)
    assert t3.locaisDeclarados[0].situacao == 'a_definir' and 'local_a_definir' in codigos(t3.pendencias)
    assert 'situacao_aguardando_processamento' in codigos(t1.pendencias)
    assert [t.turma for t in grade.turmas] == ['Turma 01'] * 3


def test_pdf_visual_retorna_os_mesmos_campos_do_print():
    png = imagem_sintetica()
    da_imagem = leitor()[0].ler(png)
    do_pdf = leitor()[0].ler(pdf_sem_texto(png))
    assert do_pdf.origem == 'pdf_visual'
    assert do_pdf.model_dump(exclude={'origem'}) == da_imagem.model_dump(exclude={'origem'})


def test_documento_completo_nao_sai_da_maquina():
    png = imagem_sintetica()
    ler, chamadas = leitor()
    ler.ler(png)
    assert len(chamadas) == 1
    recortes = [Image.open(io.BytesIO(i)) for i in chamadas[0]['imagens']]
    assert len(recortes) == 2
    for recorte in recortes:
        assert recorte.height < 150
        assert (255, 0, 0) not in set(recorte.getdata())


def test_print_cortado_indica_a_tabela_ausente_e_nao_inventa_horarios():
    grade = leitor()[0].ler(imagem_sintetica(grade=False, periodo=False))
    assert grade.semestre is None
    assert 'tabela_ausente' in codigos(grade.pendencias) and 'semestre_ausente' in codigos(grade.pendencias)
    assert all(t.encontros == [] for t in grade.turmas)


@pytest.mark.parametrize('lido', ['01', 'Turma 01', 'turma 01', ' TURMA 01 '])
def test_turma_sai_sempre_como_no_documento(lido):
    leitura = {**LEITURA, 'turmas': [{**LEITURA['turmas'][0], 'turma': lido}]}
    assert leitor(leitura=leitura)[0].ler(imagem_sintetica()).turmas[0].turma == 'Turma 01'


def test_sem_tabelas_nao_faz_segunda_chamada():
    ler, chamadas = leitor()
    grade = ler.ler(imagem_sintetica(turmas=False, grade=False))
    assert chamadas == [] and grade.turmas == []
    assert codigos(grade.pendencias).count('tabela_ausente') == 2


def test_campo_ambiguo_e_marcado_sem_preenchimento_presumido():
    leitura = {**LEITURA, 'celulas': [
        {'dia': 'seg', 'inicio': '14:00', 'fim': '15:50', 'codigo': 'FGA9OO1'},
        {'dia': 'ter', 'inicio': '14:00', 'fim': '15:50', 'codigo': 'FGA9002', 'incerto': True}],
        'turmas': [{**LEITURA['turmas'][0], 'incerto': True}]}
    grade = leitor(leitura=leitura)[0].ler(imagem_sintetica())
    assert codigos(grade.pendencias).count('leitura_incerta') == 2
    assert grade.turmas[0].encontros == [] and 'leitura_incerta' in codigos(grade.turmas[0].pendencias)
    assert [t.codigoComponente for t in grade.turmas] == ['FGA9001']


@pytest.mark.parametrize('conteudo', [b'texto qualquer', b'%PDF-1.4 quebrado'])
def test_arquivo_invalido(conteudo):
    with pytest.raises(FalhaGeracao):
        leitor()[0].ler(conteudo)


def test_sobrecarga_503_e_repetida_com_espera_e_depois_funciona(monkeypatch):
    esperas = []
    monkeypatch.setattr('rag.grade_visual.time.sleep', esperas.append)
    estados = {'n': 0}

    def handler(request):
        estados['n'] += 1
        if estados['n'] <= 2:
            return httpx.Response(503, json={'error': {'status': 'UNAVAILABLE'}})
        corpo = json.loads(request.content)
        dados = LEITURA
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(dados)}]}}]})
    ler = LeitorVisual(CONFIG, 'chave-falsa', transport=httpx.MockTransport(handler))
    assert ler.ler(imagem_sintetica()).turmas
    assert esperas == [2.0, 4.0]


def test_sobrecarga_persistente_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setattr('rag.grade_visual.time.sleep', lambda s: None)
    ler = LeitorVisual(CONFIG, 'chave-falsa', transport=httpx.MockTransport(
        lambda r: httpx.Response(503, json={'error': {'status': 'UNAVAILABLE'}})))
    with pytest.raises(FalhaGeracao):
        ler.ler(imagem_sintetica())


def test_falha_de_conexao_antes_de_chegar_ao_google_e_repetida(monkeypatch):
    monkeypatch.setattr('rag.grade_visual.time.sleep', lambda s: None)
    estados = {'n': 0}

    def handler(request):
        estados['n'] += 1
        if estados['n'] <= 2:
            raise httpx.ConnectTimeout('sem conexão', request=request)
        corpo = json.loads(request.content)
        dados = LEITURA
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(dados)}]}}]})
    ler = LeitorVisual(CONFIG, 'chave-falsa', transport=httpx.MockTransport(handler))
    assert ler.ler(imagem_sintetica()).turmas


def test_resposta_pendurada_e_repetida_com_timeout_curto(monkeypatch):
    monkeypatch.setattr('rag.grade_visual.time.sleep', lambda s: None)
    estados = {'n': 0, 'timeouts': []}

    def handler(request):
        estados['n'] += 1
        estados['timeouts'].append(request.extensions['timeout']['read'])
        if estados['n'] == 1:
            raise httpx.ReadTimeout('pendurado', request=request)
        corpo = json.loads(request.content)
        dados = LEITURA
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(dados)}]}}]})
    ler = LeitorVisual({'modelo': 'gemini-exemplo', 'timeout_s': 90}, 'chave-falsa', transport=httpx.MockTransport(handler))
    assert ler.ler(imagem_sintetica()).turmas
    assert max(estados['timeouts']) <= 30  # nunca espera 90 s por uma chamada


def test_o_tempo_total_da_leitura_e_limitado(monkeypatch):
    esperas = []
    monkeypatch.setattr('rag.grade_visual.time.sleep', esperas.append)
    monkeypatch.setattr('rag.grade_visual.PRAZO_S', 0.0)  # sem orçamento: não espera nem repete
    ler = LeitorVisual(CONFIG, 'chave-falsa', transport=httpx.MockTransport(
        lambda r: httpx.Response(503, json={'error': {'status': 'UNAVAILABLE'}})))
    with pytest.raises(FalhaGeracao):
        ler.ler(imagem_sintetica())
    assert esperas == []


def test_duas_turmas_do_mesmo_componente_preservam_salas_e_fontes_distintas():
    primeira = LEITURA['turmas'][0]
    segunda = {**primeira, 'turma': '02', 'local': 'FCTE - S10'}
    grade = leitor({**LEITURA, 'turmas': [primeira, segunda], 'celulas': LEITURA['celulas'][:1]})[0].ler(imagem_sintetica())
    assert [t.turma for t in grade.turmas] == ['Turma 01', 'Turma 02']
    assert all(not t.encontros and 'leitura_incerta' in codigos(t.pendencias) for t in grade.turmas)
    documentos = montar_trechos(grade)
    assert len({d['chunk_id'] for d in documentos}) == 2
    assert 'Turma 02' in documentos[1]['texto'] and 'S10' in documentos[1]['texto']


def test_grade_isolada_jpeg_descarta_locais_de_tabela_ausente():
    img = Image.open(io.BytesIO(imagem_sintetica(turmas=False)))
    dados = io.BytesIO()
    img.save(dados, 'JPEG')
    grade = leitor()[0].ler(dados.getvalue())
    assert grade.turmas and all(t.localTextoOriginal is None for t in grade.turmas)

@pytest.mark.parametrize('formato', ['png', 'pdf'])
def test_consulta_quarta_com_leitor_visual_e_inventario_reais(formato):
    leitura = {**LEITURA, 'turmas': LEITURA['turmas'][:1], 'celulas': [
        {'dia': 'qua', 'inicio': '14:00', 'fim': '14:55', 'codigo': 'FGA9001'}]}
    arquivo = imagem_sintetica()
    if formato == 'pdf':
        arquivo = pdf_sem_texto(arquivo)

    class Gerador:
        def gerar(self, pergunta, trechos):
            doc = next(t for t in trechos if t['source_id'] == 'COMPROVANTE')
            mapa = next(t for t in trechos if t['source_id'] == 'MAP-UAC-1')
            assert 'quarta-feira das 14:00 às 14:55' in doc['texto']
            assert 'UAC' in mapa['texto'] and 'S2' in mapa['texto']
            return resolver_resposta({'status': 'answered', 'message': '', 'claims': [
                {'text': 'Na quarta há aula às 14:00 na S2 da UAC.',
                 'chunk_ids': [doc['chunk_id'], mapa['chunk_id']]}]}, trechos)

    resposta = consultar_grade(arquivo, 'Quais aulas tenho na quarta e onde ficam as salas?',
                               leitor(leitura)[0], Gerador())
    assert resposta.respostaStatus == 'respondida'
    assert {c.origem for c in resposta.citacoes} == {'comprovante', 'base'}
