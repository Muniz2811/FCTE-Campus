"""Localização de tabelas sobre pixels, inclusive em PDFs digitalizados."""
import re
import unicodedata
from pathlib import Path
from statistics import median

import fitz
from PIL import Image

from rag.consulta.geracao import FalhaGeracao

DADOS_OCR = Path(__file__).with_name('tessdata')
COMPONENTE = re.compile(r'\b[a-z]{2,4}\s*\d{3,4}\b')
HORARIO = re.compile(r'\b\d{1,2}[:h]\d{2}\b')
IDENTIFICACAO = re.compile(r'\b(?:discente|matricula|aluno|cpf|autenticidade|verificacao|assinatura|emitido)\b')


def _linhas(imagem):
    pix = fitz.Pixmap(fitz.csRGB, imagem.width, imagem.height, imagem.tobytes(), False)
    pix.set_dpi(150, 150)
    with fitz.open(stream=pix.pdfocr_tobytes(language='por', tessdata=str(DADOS_OCR)), filetype='pdf') as doc:
        pagina = doc[0]
        escala_x = imagem.width / pagina.rect.width
        escala_y = imagem.height / pagina.rect.height
        palavras = [(x0 * escala_x, y0 * escala_y, x1 * escala_x, y1 * escala_y, palavra)
                    for x0, y0, x1, y1, palavra, *_ in pagina.get_text('words')]
    linhas = []
    for palavra in sorted(palavras, key=lambda p: (p[1] + p[3]) / 2):
        meio = (palavra[1] + palavra[3]) / 2
        if not linhas or meio - linhas[-1][0] > max(2, (palavra[3] - palavra[1]) * .55):
            linhas.append((meio, []))
        linhas[-1][1].append(palavra)
    for _, linha in linhas:
        linha.sort()
        texto = ' '.join(p[4] for p in linha).casefold()
        yield ''.join(c for c in unicodedata.normalize('NFD', texto) if not unicodedata.combining(c)), linha


def _tabela(imagem, linhas):
    if not linhas:
        return None
    palavras = [p for linha in linhas for p in linha]
    esquerda = max(0, int(min(p[0] for p in palavras)) - 2)
    direita = min(imagem.width, int(max(p[2] for p in palavras)) + 3)
    # Conserva as colunas relativas (inclusive dias vazios). O espaço entre
    # linhas é refeito em branco para excluir rodapés e blocos desconhecidos.
    faixas = [(max(0, int(min(p[1] for p in linha)) - 1),
               min(imagem.height, int(max(p[3] for p in linha)) + 2)) for linha in linhas]
    espaco = max(2, int(median(b - a for a, b in faixas) / 3))
    tabela = Image.new('RGB', (direita - esquerda, sum(b - a + espaco for a, b in faixas)), 'white')
    y = 0
    for a, b in faixas:
        tabela.paste(imagem.crop((esquerda, a, direita, b)), (0, y))
        y += b - a + espaco
    tabela.thumbnail((1800, 2400))
    return tabela


def localizar_tabelas(imagem):
    grupos = {'turmas': [], 'grade': []}
    ativo = None
    semestre = None
    try:
        for texto, palavras in _linhas(imagem):
            if IDENTIFICACAO.search(texto):
                ativo = None
                continue
            periodo = re.search(r'\bperiodo\b.{0,24}?\b(\d{4}\.[1-3])\b', texto)
            if periodo:
                semestre = periodo[1]
            if 'componente' in texto and ('turma' in texto or 'local' in texto):
                ativo = 'turmas'
            elif sum(d in texto.split() for d in ('seg', 'ter', 'qua', 'qui', 'sex', 'sab')) >= 3:
                ativo = 'grade'
            elif not ((ativo == 'turmas' and COMPONENTE.search(texto)) or
                      (ativo == 'grade' and HORARIO.search(texto))):
                continue
            grupos[ativo].append(palavras)
    except RuntimeError as exc:
        raise FalhaGeracao('Falhou a leitura local das tabelas. Confira o arquivo e o modelo de OCR.', 503) from exc
    return {k: _tabela(imagem, linhas) for k, linhas in grupos.items()}, semestre
