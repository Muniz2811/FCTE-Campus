"""Spans recentes do painel operacional; nunca recebe o conteúdo da conversa."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventoMilton(BaseModel):
    trace: UUID
    span: UUID
    parent: UUID | None = None
    etapa: Literal['Milton', 'Roteador', 'Grupo 09', 'Grupo 04', 'Transporte', 'Mapa', 'HTTP G09', 'HTTP RUmo']
    estado: Literal['executando', 'concluído', 'erro']
    inicio: datetime
    ms: int | None = Field(default=None, ge=0)
    detalhe: Literal['regras', 'llm', 'conversa', 'answered', 'insufficient', 'unavailable'] | None = None


_execucoes = OrderedDict()
_lock = Lock()
contexto = ContextVar('monitor_contexto', default=None)


def registrar(evento):
    with _lock:
        spans = _execucoes.setdefault(evento['trace'], {})
        _execucoes.move_to_end(evento['trace'])
        if len(_execucoes) > 100:
            _execucoes.popitem(last=False)
        if evento['span'] in spans or len(spans) < 128:
            spans[evento['span']] = evento.copy()


def recentes():
    with _lock:
        return [list(spans.values()) for spans in reversed(_execucoes.values())]


@contextmanager
def etapa(nome):
    contexto_atual = contexto.get()
    if contexto_atual is None:
        yield {}
        return
    trace, parent = contexto_atual
    span = str(uuid4())
    evento = dict(trace=trace, span=span, parent=parent, etapa=nome, estado='executando',
                  inicio=datetime.now(timezone.utc).isoformat())
    token = contexto.set((trace, span))
    inicio = monotonic()
    registrar(evento)
    try:
        yield evento
        evento.setdefault('resultado', 'concluído')
    except BaseException:
        evento['resultado'] = 'erro'
        raise
    finally:
        evento.update(estado=evento.pop('resultado', 'erro'), ms=round((monotonic()-inicio)*1000))
        registrar(evento)
        contexto.reset(token)
