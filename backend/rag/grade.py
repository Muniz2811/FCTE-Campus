"""Contrato da grade importada do SIGAA (issue #11).

Contrato de `POST /api/v1/grade/consultar` (rota implementada nas etapas seguintes):
  - entrada: `multipart/form-data` com `arquivo` (PDF ou imagem) e `pergunta` opcional;
  - saída: `RespostaGrade`.

Regras do contrato:
  - Fatos do documento (turmas, encontros, locais, situação) ficam em `Turma` e carregam
    `evidencias` (página ou tabela). O que foi localizado na base (fonte, título, versão)
    fica separado, em `conhecimentoDaBase`.
  - Nenhum campo de identificação do aluno (nome, matrícula, número do documento, código de
    verificação) existe aqui; `extra='forbid'` recusa qualquer campo desconhecido.
  - O comprovante lista locais por turma, não por encontro. Por isso `Encontro` não tem
    local, e várias salas ou "A definir" não são distribuídas pelos horários por suposição;
    a ausência de vínculo vira uma `Pendencia`.
  - Valores originais ("AGUARDANDO PROCESSAMENTO", "FCTE - S10 / MOCAP") são preservados
    como texto; o que for interpretado vai em campos separados e opcionais.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HORA = r'^([01]\d|2[0-3]):[0-5]\d$'


class _Modelo(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Encontro(_Modelo):
    """Faixa semanal. Horários consecutivos podem vir agrupados (14:00-15:50)."""
    dia: Literal['seg', 'ter', 'qua', 'qui', 'sex', 'sab']
    inicio: str = Field(pattern=HORA)
    fim: str = Field(pattern=HORA)


class Evidencia(_Modelo):
    """Onde, no documento, o fato foi lido."""
    tipo: Literal['pagina', 'tabela']
    referencia: str = Field(min_length=1, max_length=120)
    pagina: int | None = Field(default=None, ge=1)
    textoOriginal: str | None = Field(default=None, max_length=300)


class LocalDeclarado(_Modelo):
    """Local declarado para a turma. Não está associado a nenhum encontro."""
    textoOriginal: str = Field(min_length=1, max_length=80)
    situacao: Literal['declarado', 'a_definir'] = 'declarado'
    codigo: str | None = Field(default=None, max_length=40)
    nome: str | None = Field(default=None, max_length=120)


class VinculoBase(_Modelo):
    """Informação localizada na base do RAG, nunca lida do documento do aluno."""
    identificador: str = Field(min_length=1, max_length=80)
    titulo: str = Field(min_length=1, max_length=200)
    versaoFonte: str = Field(min_length=1, max_length=80)
    assunto: str | None = Field(default=None, max_length=200)


CodigoPendencia = Literal[
    'situacao_aguardando_processamento',
    'locais_sem_vinculo_com_encontros',
    'local_a_definir',
    'local_nao_encontrado_na_base',
    'encontros_ausentes',
    'tabela_ausente',
    'semestre_ausente',
    'leitura_incerta',
]


class Pendencia(_Modelo):
    codigo: CodigoPendencia
    mensagem: str = Field(min_length=1, max_length=300)
    codigoComponente: str | None = Field(default=None, max_length=12)


class Turma(_Modelo):
    codigoComponente: str = Field(pattern=r'^[A-Z]{2,4}\d{3,4}$')
    nomeComponente: str | None = Field(default=None, max_length=200)
    cargaHoraria: int | None = Field(default=None, ge=1, le=600)
    # Opcionais: um print cortado pode mostrar só a grade semanal, sem a tabela de turmas.
    turma: str | None = Field(default=None, max_length=20)
    situacaoOriginal: str | None = Field(default=None, max_length=80)
    encontros: list[Encontro] = Field(default_factory=list)
    localTextoOriginal: str | None = Field(default=None, max_length=120)
    locaisDeclarados: list[LocalDeclarado] = Field(default_factory=list)
    vinculoEncontrosLocais: Literal['nao_informado'] = 'nao_informado'
    evidencias: list[Evidencia] = Field(default_factory=list)
    conhecimentoDaBase: list[VinculoBase] = Field(default_factory=list)
    pendencias: list[Pendencia] = Field(default_factory=list)

    @model_validator(mode='after')
    def _locais_sem_suposicao(self):
        codigos = {p.codigo for p in self.pendencias}
        if len(self.locaisDeclarados) > 1 and self.encontros \
                and 'locais_sem_vinculo_com_encontros' not in codigos:
            raise ValueError('Mais de um local com encontros exige a pendência locais_sem_vinculo_com_encontros.')
        if any(local.situacao == 'a_definir' for local in self.locaisDeclarados) \
                and 'local_a_definir' not in codigos:
            raise ValueError('Local "A definir" exige a pendência local_a_definir.')
        return self


class GradeImportada(_Modelo):
    versaoContrato: Literal['1'] = '1'
    semestre: str | None = Field(default=None, pattern=r'^\d{4}\.[1-3]$')
    curso: str | None = Field(default=None, max_length=200)
    origem: Literal['pdf_texto', 'pdf_visual', 'imagem', 'formulario']
    status: Literal['completa', 'parcial']
    turmas: list[Turma] = Field(max_length=40)
    pendencias: list[Pendencia] = Field(default_factory=list)

    @model_validator(mode='after')
    def _status_coerente(self):
        ha_pendencia = bool(self.pendencias) or any(t.pendencias for t in self.turmas)
        if self.status == 'completa' and ha_pendencia:
            raise ValueError('Grade com pendências deve ter status parcial.')
        return self


class RespostaGrade(_Modelo):
    grade: GradeImportada
    pergunta: str | None = Field(default=None, max_length=1200)
    resposta: str | None = None
    fontes: list[VinculoBase] = Field(default_factory=list)
