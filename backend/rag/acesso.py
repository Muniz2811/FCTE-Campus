"""Chat público e token Bearer para comunicação entre serviços."""
import os
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from fastapi import HTTPException
from fastapi.security import HTTPBearer
from starlette.responses import JSONResponse

from rag.config import caminho_projeto

LOCAL_HOSTS = {'127.0.0.1', 'localhost', '[::1]'}
# Rotas entre serviços. O chat web e a comparação ao vivo continuam públicos por decisão do projeto.
ROTAS_PROTEGIDAS = {'/perguntar', '/api/v1/multiagent'}


@dataclass
class Acesso:
    obrigatorio: bool = False
    token: str = field(default='', repr=False)
    falhas: dict = field(default_factory=dict, repr=False)
    trava: threading.Lock = field(default_factory=threading.Lock, repr=False)
    somente_integracao: bool = False

    def __post_init__(self):
        if self.obrigatorio and len(self.token) < 32:
            raise ValueError('Configure RAG_API_TOKEN com 32 ou mais caracteres.')
        if self.obrigatorio and not self.token.isascii():
            raise ValueError('Use um token ASCII para a integração Bearer.')

    @classmethod
    def do_ambiente(cls):
        arquivo = Path(os.environ.get('RAG_ENV_FILE', caminho_projeto('.env')))
        valores = dotenv_values(arquivo) if arquivo.is_file() else {}
        def obter(nome, padrao=''):
            return os.environ.get(nome, valores.get(nome) or padrao)
        hosts = {h.strip() for h in obter('RAG_ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',') if h.strip()}
        publico = bool(hosts - LOCAL_HOSTS) or os.environ.get('RENDER', '').lower() == 'true'
        flag = obter('RAG_REQUIRE_AUTH', 'true' if publico else 'false').strip().lower()
        if flag not in {'true', 'false'}:
            raise ValueError('RAG_REQUIRE_AUTH deve ser true ou false.')
        obrigatorio = flag == 'true'
        if publico and not obrigatorio:
            raise ValueError('Hospedagem pública exige RAG_REQUIRE_AUTH=true.')
        api_only = obter('RAG_API_ONLY', 'false').strip().lower()
        if api_only not in {'true', 'false'}:
            raise ValueError('RAG_API_ONLY deve ser true ou false.')
        if api_only == 'true' and not obrigatorio:
            raise ValueError('RAG_API_ONLY exige RAG_REQUIRE_AUTH=true.')
        return cls(obrigatorio, obter('RAG_API_TOKEN'), somente_integracao=api_only == 'true')

    async def proteger(self, request):
        if not self.obrigatorio or request.url.path not in ROTAS_PROTEGIDAS:
            return None
        ip = request.client.host if request.client else 'desconhecido'
        agora = time.monotonic()
        with self.trava:
            if len(self.falhas) >= 2048:
                self.falhas = {k: v for k, v in self.falhas.items() if v and v[-1] > agora - 60}
                if len(self.falhas) >= 2048:
                    self.falhas.pop(next(iter(self.falhas)))
            falhas = self.falhas.setdefault(ip, deque(maxlen=10))
            while falhas and falhas[0] <= agora - 60:
                falhas.popleft()
            if len(falhas) >= 10:
                return JSONResponse({'detail': 'Muitas tentativas de acesso. Aguarde um minuto.'},
                                    status_code=429, headers={'Retry-After': '60'})
        valido = False
        try:
            bearer = await HTTPBearer(auto_error=False)(request)
            if bearer:
                valido = secrets.compare_digest(bearer.credentials.encode(), self.token.encode())
        except HTTPException:
            pass
        if valido:
            return None
        # Contabiliza tentativas com credenciais inválidas.
        if request.headers.get('authorization'):
            with self.trava:
                falhas.append(agora)
        return JSONResponse({'detail': 'Acesso não autorizado.'}, status_code=401,
                            headers={'WWW-Authenticate': 'Bearer', 'Cache-Control': 'no-store'})
