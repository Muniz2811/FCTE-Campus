"""Vincula os locais da grade ao inventário e à base do Grupo 09 (issue #14).

Regras:
  - Só fontes do catálogo aprovado do Grupo 09 são usadas: as fichas do mapa (MAP-*) e os
    trechos do corpus; nada vem de conhecimento do modelo.
  - Código ou nome exato no inventário de ambientes dá a localização completa (prédio e andar).
  - Sem ficha de mapa, um local só ganha o prédio quando uma frase do corpus que cita o código
    cita exatamente um prédio (UAC ou UED); o andar fica em aberto.
  - Vários locais ("S10 / MOCAP") são tratados um a um; "A definir", código desconhecido ou
    ambíguo viram pendências, sem escolher por suposição.
  - O texto original do comprovante nunca é alterado.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rag.armazenamento.manifesto import hash_bytes
from rag.config import caminho_projeto, carregar_config
from rag.grade import GradeImportada, LocalizacaoBase, Pendencia, VinculoBase
from rag.ingestao.catalogo import fonte_indexavel, ler_catalogo

PREDIOS = re.compile(r'\b(UAC|UED)\b')
CODIGO_TEXTUAL = re.compile(r'^[A-Za-z]{4,}$')  # códigos curtos como "S5" só valem no mapa
FRASES = re.compile(r'(?<=[.;:])\s+|\n')


def _chave(texto: str) -> str:
    normal = ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', normal)


@dataclass(frozen=True)
class Ambiente:
    id: str
    nome: str
    predio: str
    andar: str
    nivel: int
    fonte: VinculoBase
    limitacoes: str | None


@dataclass(frozen=True)
class Trecho:
    texto: str
    fonte: VinculoBase


class Inventario:
    def __init__(self, ambientes: list[Ambiente], trechos: list[Trecho]):
        self.ambientes, self.trechos = ambientes, trechos

    @classmethod
    def carregar(cls, config: dict) -> 'Inventario':
        fontes = {f['source_id']: f for f in ler_catalogo(caminho_projeto(config['caminhos']['catalogo']))
                  if fonte_indexavel(f)}

        def vinculo(sid, assunto=None):
            f = fontes[sid]
            return VinculoBase(identificador=sid, titulo=f['titulo'], versaoFonte=f['versao'], assunto=assunto)

        ambientes = []
        for arquivo in sorted(caminho_projeto('data/imports/mapas').glob('MAP-*.json')):
            dados = arquivo.read_bytes()
            ficha = json.loads(dados)
            fonte = fontes.get(ficha['source_id'])
            if fonte is None or fonte['sha256'] != hash_bytes(dados):
                raise ValueError('Ficha do mapa ausente do catálogo ou com hash divergente')
            for a in ficha['ambientes']:
                ambientes.append(Ambiente(
                    id=a['id'], nome=a['nome'], predio=ficha['predio'], andar=ficha['andar']['nome'],
                    nivel=ficha['andar']['nivel'], fonte=vinculo(ficha['source_id'], f'{a["nome"]} ({a["id"]})'),
                    limitacoes=ficha.get('limitacoes')))
        trechos = []
        for linha in caminho_projeto(config['caminhos']['chunks']).read_text(encoding='utf-8').splitlines():
            if not linha.strip():
                continue
            c = json.loads(linha)
            if c['source_id'] in fontes and not c['source_id'].startswith('MAP-'):
                trechos.append(Trecho(c['texto'], vinculo(c['source_id'], c['titulo'])))
        return cls(ambientes, trechos)

    def no_mapa(self, codigo: str) -> list[Ambiente]:
        chave = _chave(codigo)
        return [a for a in self.ambientes if chave and chave in (_chave(a.nome), _chave(a.id))]

    def predios_no_texto(self, codigo: str) -> list[tuple[str, VinculoBase]]:
        """Prédio citado na mesma frase que o código, quando a frase cita um só."""
        if not CODIGO_TEXTUAL.match(codigo):
            return []
        palavra = re.compile(rf'\b{re.escape(codigo)}\b', re.I)
        achados = []
        for trecho in self.trechos:
            for frase in FRASES.split(trecho.texto):
                if palavra.search(frase):
                    predios = set(PREDIOS.findall(frase))
                    if len(predios) == 1:
                        achados.append((predios.pop(), trecho.fonte))
        return achados


@lru_cache(maxsize=1)
def _inventario_padrao() -> Inventario:
    return Inventario.carregar(carregar_config())


def enriquecer_grade(grade: GradeImportada, inventario: Inventario | None = None) -> GradeImportada:
    inventario = inventario or _inventario_padrao()
    turmas = []
    for turma in grade.turmas:
        localizacoes, pendencias = [], list(turma.pendencias)

        def pend(codigo, mensagem):
            if not any(p.codigo == codigo and p.mensagem == mensagem for p in pendencias):
                pendencias.append(Pendencia(codigo=codigo, mensagem=mensagem, codigoComponente=turma.codigoComponente))

        for local in turma.locaisDeclarados:
            if local.situacao == 'a_definir':
                continue  # já registrado como pendência na leitura
            codigo = local.codigo or local.textoOriginal
            ambientes = inventario.no_mapa(codigo)
            if len(ambientes) == 1:
                a = ambientes[0]
                localizacoes.append(LocalizacaoBase(
                    textoOriginal=local.textoOriginal, predio=a.predio, andar=a.andar, nivel=a.nivel,
                    ambienteId=a.id, evidencia='mapa', precisao='ambiente', fonte=a.fonte, limitacoes=a.limitacoes))
                continue
            if len(ambientes) > 1:
                pend('local_ambiguo_na_base', f'O código "{codigo}" corresponde a mais de um ambiente do inventário.')
                continue
            predios = inventario.predios_no_texto(codigo)
            nomes = {p for p, _ in predios}
            if len(nomes) == 1:
                predio, fonte = predios[0]
                localizacoes.append(LocalizacaoBase(
                    textoOriginal=local.textoOriginal, predio=predio, evidencia='texto', precisao='predio', fonte=fonte))
            elif len(nomes) > 1:
                pend('local_ambiguo_na_base', f'A base cita "{codigo}" em mais de um prédio.')
            else:
                pend('local_nao_encontrado_na_base', f'O local "{local.textoOriginal}" não consta na base do Grupo 09.')
        turmas.append(turma.model_copy(update={'localizacoes': localizacoes, 'pendencias': pendencias}))
    return GradeImportada.model_validate(grade.model_copy(update={'turmas': turmas}).model_dump())
