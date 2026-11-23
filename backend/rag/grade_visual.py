"""Leitor visual da grade do SIGAA (issue #13): PNG/JPEG e PDF sem texto selecionável.

Opção adotada: modelo visual (Gemini), em duas chamadas, para que o documento completo
nunca saia da máquina:

  1. Localização: recebe apenas uma miniatura sem legibilidade (lado maior de 360 px) e devolve
     as caixas das tabelas. Nome, matrícula e códigos do cabeçalho não são legíveis nela.
  2. Extração: recebe somente os recortes em resolução normal da tabela de turmas, da grade
     semanal e da linha do período, e devolve o que está legível.

O modelo só transcreve. Fusão de horários, separação de locais, pendências e o contrato final
são feitos aqui, de forma determinística. Nada é gravado em disco ou em log: imagens, textos
lidos e identificadores existem apenas em memória durante a chamada. PDFs: só a primeira página.
"""
from __future__ import annotations

import base64
import io
import json
import re
from typing import Literal

import fitz
import httpx
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rag.consulta.geracao import FalhaGeracao
from rag.grade import Encontro, Evidencia, GradeImportada, LocalDeclarado, Pendencia, Turma

LIMITE_BYTES = 8 * 1024 * 1024
LIMITE_LADO = 6000
LADO_MINIATURA = 360
LADO_MAX_RECORTE = 1800
TENTATIVAS = 3
MARGEM = 8                # em milésimos da imagem, ao redor de cada recorte
TOLERANCIA_FUSAO_MIN = 10  # a grade do SIGAA deixa 5 min entre 18:55 e 19:00
DIAS = ('seg', 'ter', 'qua', 'qui', 'sex', 'sab')
HORA = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
CODIGO = re.compile(r'^[A-Z]{2,4}\d{3,4}$')
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent'


class _Modelo(BaseModel):
    model_config = ConfigDict(extra='forbid')


class _Caixa(_Modelo):
    """Coordenadas de 0 a 1000, relativas à imagem."""
    ymin: int = Field(ge=0, le=1000)
    xmin: int = Field(ge=0, le=1000)
    ymax: int = Field(ge=0, le=1000)
    xmax: int = Field(ge=0, le=1000)


class _Localizacao(_Modelo):
    tabela_turmas: _Caixa | None = None
    tabela_grade: _Caixa | None = None
    periodo: _Caixa | None = None


class _LinhaTurma(_Modelo):
    codigo: str
    nome: str | None = None
    carga_horaria: int | None = None
    turma: str | None = None
    local: str | None = None
    situacao: str | None = None
    incerto: bool = False


class _Celula(_Modelo):
    dia: Literal['seg', 'ter', 'qua', 'qui', 'sex', 'sab']
    inicio: str
    fim: str
    codigo: str
    incerto: bool = False


class _Leitura(_Modelo):
    semestre: str | None = None
    turmas: list[_LinhaTurma] = Field(default_factory=list)
    celulas: list[_Celula] = Field(default_factory=list)


PROMPT_LOCALIZAR = (
    'A imagem é uma miniatura de um comprovante de matrícula do SIGAA. Localize três regiões: '
    '"tabela_turmas" (tabela Turmas selecionadas, com Componente Curricular, Turma, Local e Situação, '
    'incluindo o cabeçalho da tabela), "tabela_grade" (tabela semanal com Horários e Seg a Sáb) e '
    '"periodo" (somente a linha com o título do período, como "Período 2025.1"). Use coordenadas de 0 a '
    '1000 [ymin, xmin, ymax, xmax] relativas à imagem. NÃO inclua nas caixas o bloco com dados do '
    'discente (matrícula, nome, curso). Se uma região não aparece, devolva null para ela. Não invente.')

PROMPT_EXTRAIR = (
    'As imagens são recortes de um comprovante de matrícula do SIGAA: a tabela de turmas, a grade semanal '
    'e, às vezes, a linha do período. Transcreva SOMENTE o que está legível. '
    'turmas: uma entrada por linha, com codigo (como FGA0109), nome, carga_horaria em horas, turma, local '
    'e situacao exatamente como escritos. celulas: uma entrada por célula ocupada da grade semanal, com '
    'dia (seg a sab), inicio e fim da faixa da linha em HH:MM e o codigo escrito na célula; ignore "---". '
    'semestre no formato AAAA.N, apenas se a linha do período estiver visível. Se um campo estiver '
    'ilegível, ambíguo ou cortado, deixe-o null, ou marque incerto=true quando houver um palpite parcial; '
    'nunca complete, corrija ou presuma valores. Se uma tabela não aparece, devolva a lista vazia. '
    'Não transcreva nome, matrícula, número do documento nem código de verificação.')


def _tipo(conteudo: bytes) -> Literal['png', 'jpeg', 'pdf']:
    if conteudo.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if conteudo.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if conteudo.startswith(b'%PDF-'):
        return 'pdf'
    raise FalhaGeracao('Envie uma imagem PNG/JPEG ou um PDF.', 415)


def _para_imagem(conteudo: bytes) -> tuple[Image.Image, Literal['imagem', 'pdf_visual']]:
    if len(conteudo) > LIMITE_BYTES:
        raise FalhaGeracao('O arquivo excede o limite de 8 MB.', 413)
    tipo = _tipo(conteudo)
    try:
        if tipo == 'pdf':
            with fitz.open(stream=conteudo, filetype='pdf') as doc:
                if doc.page_count < 1:
                    raise FalhaGeracao('O PDF não tem páginas.', 422)
                pagina = doc[0]
                escala = min(200 / 72, LIMITE_LADO / max(pagina.rect.width, pagina.rect.height))
                pix = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala), alpha=False)
                imagem = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            return imagem, 'pdf_visual'
        imagem = Image.open(io.BytesIO(conteudo))
        if max(imagem.size) > LIMITE_LADO:
            raise FalhaGeracao('A imagem é grande demais. Use no máximo 6000 px de lado.', 413)
        return imagem.convert('RGB'), 'imagem'  # reencodar descarta metadados (EXIF)
    except (UnidentifiedImageError, OSError, ValueError, RuntimeError, fitz.FileDataError):
        raise FalhaGeracao('Não foi possível abrir o arquivo enviado.', 422) from None


def _png(imagem: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    return buffer.getvalue()


def _miniatura(imagem: Image.Image) -> bytes:
    copia = imagem.convert('L')
    copia.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
    return _png(copia)


def _recortar(imagem: Image.Image, caixa: _Caixa | None) -> Image.Image | None:
    if caixa is None or caixa.ymin >= caixa.ymax or caixa.xmin >= caixa.xmax:
        return None  # caixa ausente ou incoerente: não adivinhar a região
    largura, altura = imagem.size
    x0, y0 = max(caixa.xmin - MARGEM, 0), max(caixa.ymin - MARGEM, 0)
    x1, y1 = min(caixa.xmax + MARGEM, 1000), min(caixa.ymax + MARGEM, 1000)
    recorte = imagem.crop((round(x0 * largura / 1000), round(y0 * altura / 1000),
                           round(x1 * largura / 1000), round(y1 * altura / 1000)))
    if recorte.width < 40 or recorte.height < 12:
        return None
    recorte.thumbnail((LADO_MAX_RECORTE, LADO_MAX_RECORTE))
    return recorte


def _minutos(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def _fundir(celulas: list[_Celula]) -> list[Encontro]:
    """Une faixas consecutivas do mesmo dia (14:00-14:55 e 14:55-15:50 viram 14:00-15:50)."""
    encontros: list[Encontro] = []
    for dia in DIAS:
        faixas = sorted(((c.inicio, c.fim) for c in celulas if c.dia == dia), key=lambda f: _minutos(f[0]))
        atual = None
        for inicio, fim in faixas:
            if atual and 0 <= _minutos(inicio) - _minutos(atual[1]) <= TOLERANCIA_FUSAO_MIN:
                atual = (atual[0], max(atual[1], fim, key=_minutos))
            else:
                if atual:
                    encontros.append(Encontro(dia=dia, inicio=atual[0], fim=atual[1]))
                atual = (inicio, fim)
        if atual:
            encontros.append(Encontro(dia=dia, inicio=atual[0], fim=atual[1]))
    return encontros


def _locais(texto: str | None) -> list[LocalDeclarado]:
    if not texto or not texto.strip():
        return []
    locais = []
    for parte in re.split(r'\s*/\s*', texto.strip()):
        if not parte:
            continue
        if re.fullmatch(r'a\s+definir', parte, re.I):
            locais.append(LocalDeclarado(textoOriginal=parte, situacao='a_definir'))
            continue
        codigo = re.sub(r'^FCTE\s*-\s*', '', parte, flags=re.I).strip()
        locais.append(LocalDeclarado(textoOriginal=parte, codigo=codigo or None))
    return locais


def montar_grade(leitura: _Leitura, origem: str, *, tabela_turmas: bool, tabela_grade: bool,
                 periodo_visivel: bool) -> GradeImportada:
    """Converte a transcrição do modelo no contrato, sem preencher o que não foi lido."""
    pendencias: list[Pendencia] = []
    if not tabela_turmas:
        pendencias.append(Pendencia(codigo='tabela_ausente', mensagem='A tabela de turmas não aparece no arquivo.'))
    if not tabela_grade:
        pendencias.append(Pendencia(codigo='tabela_ausente', mensagem='A grade semanal não aparece no arquivo.'))
    semestre = leitura.semestre if leitura.semestre and re.fullmatch(r'\d{4}\.[1-3]', leitura.semestre) else None
    if semestre is None:
        pendencias.append(Pendencia(
            codigo='semestre_ausente' if not periodo_visivel else 'leitura_incerta',
            mensagem='O período não aparece no arquivo.' if not periodo_visivel
            else 'O período não pôde ser lido com segurança.'))

    celulas_validas: list[_Celula] = []
    for celula in leitura.celulas:
        codigo = celula.codigo.strip().upper()
        if celula.incerto or not CODIGO.match(codigo) or not HORA.match(celula.inicio) or not HORA.match(celula.fim) \
                or _minutos(celula.fim) <= _minutos(celula.inicio):
            pendencias.append(Pendencia(codigo='leitura_incerta', mensagem=(
                f'Uma célula da grade semanal ({celula.dia}) está ilegível ou ambígua e não foi usada.')))
            continue
        celulas_validas.append(celula.model_copy(update={'codigo': codigo}))

    ordem: list[str] = []
    linhas: dict[str, _LinhaTurma | None] = {}
    for linha in leitura.turmas:
        codigo = linha.codigo.strip().upper()
        if not CODIGO.match(codigo):
            pendencias.append(Pendencia(codigo='leitura_incerta', mensagem=(
                'Um código de componente na tabela de turmas está ilegível ou ambíguo e a linha não foi usada.')))
            continue
        if codigo not in linhas:
            ordem.append(codigo)
        linhas[codigo] = linha
    for celula in celulas_validas:
        if celula.codigo not in linhas:
            ordem.append(celula.codigo)
            linhas[celula.codigo] = None

    turmas = []
    for codigo in ordem:
        linha = linhas[codigo]
        encontros = _fundir([c for c in celulas_validas if c.codigo == codigo])
        locais = _locais(linha.local) if linha else []
        p: list[Pendencia] = []

        def pend(cod, msg):
            p.append(Pendencia(codigo=cod, mensagem=msg, codigoComponente=codigo))

        if linha and linha.incerto:
            pend('leitura_incerta', 'A linha desta turma está parcialmente ilegível; confira o documento.')
        if linha and linha.situacao and 'aguardando' in linha.situacao.lower():
            pend('situacao_aguardando_processamento', 'A matrícula nesta turma ainda aguarda processamento.')
        if len(locais) > 1 and encontros:
            pend('locais_sem_vinculo_com_encontros',
                 'O documento lista mais de um local sem dizer qual encontro usa qual.')
        if any(local.situacao == 'a_definir' for local in locais):
            pend('local_a_definir', 'O local ainda não foi definido no documento.')
        if tabela_grade and not encontros:
            pend('encontros_ausentes', 'Nenhum horário desta turma foi lido na grade semanal.')
        evidencias = []
        if linha:
            evidencias.append(Evidencia(tipo='tabela', referencia='Turmas selecionadas', pagina=1))
        if encontros:
            evidencias.append(Evidencia(tipo='tabela', referencia='Grade semanal', pagina=1))
        turmas.append(Turma(
            codigoComponente=codigo, nomeComponente=(linha.nome or None) if linha else None,
            cargaHoraria=linha.carga_horaria if linha and linha.carga_horaria and 0 < linha.carga_horaria <= 600 else None,
            turma=(linha.turma or None) if linha else None,
            situacaoOriginal=(linha.situacao or None) if linha else None,
            encontros=encontros, localTextoOriginal=(linha.local or None) if linha else None,
            locaisDeclarados=locais, evidencias=evidencias, pendencias=p))
    return GradeImportada(
        semestre=semestre, origem=origem, turmas=turmas, pendencias=pendencias,
        status='parcial' if pendencias or any(t.pendencias for t in turmas) else 'completa')


class LeitorVisual:
    def __init__(self, config, chave, transport=None):
        if not re.fullmatch(r'[a-zA-Z0-9.-]+', config['modelo'] or ''):
            raise ValueError('Configure um modelo Gemini válido')
        self.config, self.chave = config, (chave or '').strip()
        self.cliente = httpx.Client(timeout=config['timeout_s'], transport=transport)

    def close(self):
        self.cliente.close()

    def _chamar(self, instrucao: str, imagens: list[bytes], esquema: dict, max_tokens: int) -> dict:
        if not self.chave:
            raise FalhaGeracao('Configure GEMINI_API_KEY no ambiente do backend RAG.', 503)
        partes = [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(i).decode()}} for i in imagens]
        corpo = {'systemInstruction': {'parts': [{'text': instrucao}]},
                 'contents': [{'role': 'user', 'parts': partes}],
                 'generationConfig': {'temperature': 0, 'maxOutputTokens': max_tokens,
                                      'responseMimeType': 'application/json', 'responseJsonSchema': esquema}}
        resposta = None
        for tentativa in range(TENTATIVAS):  # reconexões e 5xx passageiros; timeout e 429 não repetem
            try:
                resposta = self.cliente.post(ENDPOINT.format(self.config['modelo']),
                                             headers={'x-goog-api-key': self.chave}, json=corpo)
            except httpx.TimeoutException:
                raise FalhaGeracao('O Gemini demorou a responder. Tente novamente.', 504) from None
            except httpx.RequestError:
                if tentativa == TENTATIVAS - 1:
                    raise FalhaGeracao('Não foi possível conectar ao Gemini. Confira sua internet.', 503) from None
                continue
            if resposta.status_code in (500, 502, 503, 504) and tentativa < TENTATIVAS - 1:
                continue
            break
        if resposta.status_code == 429:
            raise FalhaGeracao('Limite do Gemini atingido. Aguarde e confira a cota.', 429)
        if resposta.status_code in (400, 401, 403, 404):
            raise FalhaGeracao('O Gemini recusou a chamada. Confira a chave, o modelo e as permissões.', 503)
        if not resposta.is_success:
            raise FalhaGeracao('O Gemini está indisponível. Tente novamente mais tarde.', 502)
        try:
            candidato = resposta.json()['candidates'][0]
            if candidato.get('finishReason') != 'STOP':
                raise ValueError
            texto = ''.join(p.get('text', '') for p in candidato['content']['parts'] if not p.get('thought'))
            return json.loads(texto)
        except (ValueError, KeyError, IndexError, TypeError):
            raise FalhaGeracao('O Gemini retornou uma leitura incompleta ou inválida. Tente outro arquivo.') from None

    def ler(self, conteudo: bytes) -> GradeImportada:
        imagem, origem = _para_imagem(conteudo)
        try:
            local = _Localizacao.model_validate(
                self._chamar(PROMPT_LOCALIZAR, [_miniatura(imagem)], _Localizacao.model_json_schema(), 1000))
        except ValidationError:
            raise FalhaGeracao('Não foi possível localizar as tabelas no arquivo.') from None
        recortes = {nome: _recortar(imagem, getattr(local, nome)) for nome in ('tabela_turmas', 'tabela_grade', 'periodo')}
        presentes = [r for r in recortes.values() if r is not None]
        if not recortes['tabela_turmas'] and not recortes['tabela_grade']:
            return montar_grade(_Leitura(), origem, tabela_turmas=False, tabela_grade=False, periodo_visivel=False)
        try:
            leitura = _Leitura.model_validate(
                self._chamar(PROMPT_EXTRAIR, [_png(r) for r in presentes], _Leitura.model_json_schema(), 4000))
        except ValidationError:
            raise FalhaGeracao('O Gemini retornou uma leitura inválida. Tente outro arquivo.') from None
        return montar_grade(leitura, origem, tabela_turmas=recortes['tabela_turmas'] is not None,
                            tabela_grade=recortes['tabela_grade'] is not None,
                            periodo_visivel=recortes['periodo'] is not None)
