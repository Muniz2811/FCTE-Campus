"""HTTP Basic para o chat e Bearer para comunicação entre serviços."""
import os
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from fastapi import HTTPException
from fastapi.security import HTTPBasic, HTTPBearer
from starlette.responses import JSONResponse

from rag.config import caminho_projeto

LOCAL_HOSTS = {'127.0.0.1', 'localhost', '[::1]'}


@dataclass
class Acesso:
    obrigatorio: bool = False
    token: str = field(default='', repr=False)
    usuario: str = 'equipe'
    senha: str = field(default='', repr=False)
    falhas: dict = field(default_factory=dict, repr=False)
    trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        if self.obrigatorio and (len(self.token) < 32 or len(self.senha) < 16 or not self.usuario):
            raise ValueError('Configure RAG_API_TOKEN (32+ caracteres), RAG_WEB_USER e RAG_WEB_PASSWORD (16+).')
        if self.obrigatorio and not all(v.isascii() for v in (self.token, self.usuario, self.senha)):
            raise ValueError('Use usuário, senha e token ASCII para o login HTTP Basic e Bearer.')

    @classmethod
    def do_ambiente(cls):
        arquivo = Path(os.environ.get('RAG_ENV_FILE', caminho_projeto('.env')))
        valores = dotenv_values(arquivo) if arquivo.is_file() else {}
        def obter(nome, padrao=''):
            return os.environ.get(nome, valores.get(nome) or padrao)
        hosts = {h.strip() for h in os.environ.get('RAG_ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',') if h.strip()}
        publico = bool(hosts - LOCAL_HOSTS) or os.environ.get('RENDER', '').lower() == 'true'
        flag = obter('RAG_REQUIRE_AUTH', 'true' if publico else 'false').strip().lower()
        if flag not in {'true', 'false'}:
            raise ValueError('RAG_REQUIRE_AUTH deve ser true ou false.')
        obrigatorio = flag == 'true'
        if publico and not obrigatorio:
            raise ValueError('Hospedagem pública exige RAG_REQUIRE_AUTH=true.')
        return cls(obrigatorio, obter('RAG_API_TOKEN'), obter('RAG_WEB_USER', 'equipe'), obter('RAG_WEB_PASSWORD'))

    async def proteger(self, request):
        if not self.obrigatorio:
            return None
        caminho = request.url.path
        servico = caminho == '/perguntar'
        protegido = servico or caminho in {'/', '/index.html'} or caminho.startswith(
            ('/api/v1/chat', '/api/v1/comparison'))
        if not protegido:
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
            if not servico and not valido:
                basic = await HTTPBasic(auto_error=False)(request)
                if basic:
                    nome_ok = secrets.compare_digest(basic.username.encode(), self.usuario.encode())
                    senha_ok = secrets.compare_digest(basic.password.encode(), self.senha.encode())
                    valido = nome_ok and senha_ok
        except HTTPException:
            pass
        if valido:
            return None
        # Não contabiliza o primeiro desafio do navegador, sem credenciais.
        if request.headers.get('authorization'):
            with self.trava:
                falhas.append(agora)
        esquema = 'Bearer' if servico else 'Basic realm="FCTE Campus"'
        return JSONResponse({'detail': 'Acesso não autorizado.'}, status_code=401,
                            headers={'WWW-Authenticate': esquema, 'Cache-Control': 'no-store'})
