"""Adaptador pgvector via Data API do Supabase; credenciais só no backend."""
import json
from urllib.parse import urlsplit

import httpx

from rag.config import ambiente_backend
from rag.armazenamento.indice import metadados_chunk


class IndiceSupabase:
    def __init__(self, colecao: str):
        ambiente = ambiente_backend()
        url = (ambiente.get('SUPABASE_URL') or '').strip().rstrip('/')
        partes = urlsplit(url)
        if (partes.scheme != 'https' or not partes.hostname or partes.username
                or partes.password or partes.path or partes.query or partes.fragment):
            raise ValueError('Configure SUPABASE_URL com a URL HTTPS do projeto, sem caminhos')
        chave = (ambiente.get('SUPABASE_SECRET_KEY') or ambiente.get('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
        if not chave or chave.startswith('sb_publishable_'):
            raise ValueError('Configure SUPABASE_SECRET_KEY no backend com chave secret ou service_role')
        self.url = url + '/rest/v1/'
        self.headers = {'apikey': chave}
        # As novas secret keys não são JWTs; não enviá-las como Bearer.
        if not chave.startswith('sb_secret_'):
            self.headers['Authorization'] = 'Bearer ' + chave
        self.colecao = colecao

    def _requisitar(self, metodo, recurso, **kwargs):
        try:
            with httpx.Client(base_url=self.url, headers=self.headers, timeout=60,
                              follow_redirects=False) as cliente:
                resposta = cliente.request(metodo, recurso, **kwargs)
        except httpx.HTTPError:
            raise OSError('Supabase inacessível ou sem resposta. Confira conexão e estado do projeto.') from None
        if resposta.is_error:
            dicas = {401: 'Confira a chave secreta.', 403: 'Confira a chave service_role e as permissões.',
                     404: 'Execute backend/supabase/setup.sql no SQL Editor.',
                     400: 'Confira a versão do SQL e a dimensão dos vetores.'}
            raise OSError(f'Supabase HTTP {resposta.status_code}. '
                          + dicas.get(resposta.status_code, 'Confira o SQL e os logs do projeto.'))
        return resposta

    def manifesto(self) -> dict:
        linhas = self._requisitar('GET', 'fcte_rag_colecoes', params={
            'colecao': 'eq.' + self.colecao, 'select': 'manifesto', 'limit': '1'}).json()
        if not linhas:
            raise ValueError('Coleção ausente no Supabase. Execute a migração com --enviar primeiro.')
        return linhas[0]['manifesto']

    def manifesto_ativo(self, colecao_logica: str) -> dict:
        linhas = self._requisitar('GET', 'fcte_rag_colecoes', params={
            'colecao_logica': 'eq.' + colecao_logica, 'ativa': 'eq.true',
            'select': 'manifesto', 'limit': '1'}).json()
        if not linhas:
            raise ValueError('Nenhuma base ativa no Supabase. Execute a migração com --enviar.')
        manifesto = linhas[0]['manifesto']
        self.colecao = manifesto['indice']['colecao']
        return manifesto

    def manifesto_compativel(self, colecao_logica: str, sha_chunks: str, sha_catalogo: str) -> dict:
        """Cada deploy abre seu snapshot, inclusive durante uma atualização gradual."""
        linhas = self._requisitar('GET', 'fcte_rag_colecoes', params={
            'colecao_logica': 'eq.' + colecao_logica,
            'manifesto->corpus->>sha256_chunks': 'eq.' + sha_chunks,
            'manifesto->corpus->>sha256_catalogo': 'eq.' + sha_catalogo,
            'select': 'manifesto', 'order': 'ativa.desc,publicado_em.desc', 'limit': '1'}).json()
        if not linhas:
            raise ValueError('Esta versão do corpus ainda não está no Supabase. '
                             'Prepare o índice e execute rag:migrate -- --preparar.')
        manifesto = linhas[0]['manifesto']
        self.colecao = manifesto['indice']['colecao']
        return manifesto

    def contar(self) -> int:
        resposta = self._requisitar('HEAD', 'fcte_rag_chunks', params={
            'colecao': 'eq.' + self.colecao, 'select': 'chunk_id'}, headers={'Prefer': 'count=exact'})
        return int(resposta.headers['content-range'].rsplit('/', 1)[1])

    def _linhas(self, campos: str) -> list[dict]:
        linhas = []
        while True:
            pagina = self._requisitar('GET', 'fcte_rag_chunks', params={
                'colecao': 'eq.' + self.colecao, 'select': campos, 'order': 'chunk_id',
                'limit': '500', 'offset': str(len(linhas))}).json()
            linhas.extend(pagina)
            if not pagina:
                return linhas

    def ids(self) -> set[str]:
        return {r['chunk_id'] for r in self._linhas('chunk_id')}

    def exportar_vetores(self):
        from rag.armazenamento.embeddings import validar_vetores
        linhas = self._linhas('chunk_id,embedding')
        vetores = [json.loads(r['embedding']) if isinstance(r['embedding'], str)
                   else r['embedding'] for r in linhas]
        return [r['chunk_id'] for r in linhas], validar_vetores(vetores, len(linhas), 384)

    @staticmethod
    def _trecho(linha):
        meta = dict(linha['metadados'])
        secoes = json.loads(meta.pop('secoes_json'))
        entidades = json.loads(meta.pop('entidades_json'))
        return {**meta, 'chunk_id': linha['chunk_id'], 'texto': linha['texto'],
                'secoes': secoes, 'entidades': entidades}

    def textos(self) -> list[dict]:
        """O perfil BM25 não transfere vetores nem chama a RPC vetorial."""
        return [self._trecho(linha) for linha in self._linhas('chunk_id,texto,metadados')]

    def publicar(self, chunks: list[dict], vetores, manifesto: dict) -> None:
        from rag.armazenamento.embeddings import validar_vetores
        if manifesto['indice']['colecao'] != self.colecao:
            raise ValueError('Manifesto pertence a outra coleção')
        if manifesto['embeddings']['dimensao'] != 384:
            raise ValueError('O SQL desta migração exige 384 dimensões')
        matriz = validar_vetores(vetores, len(chunks), 384)
        ids = [c['chunk_id'] for c in chunks]
        if not chunks or len(set(ids)) != len(ids) or len(chunks) != manifesto['indice']['total']:
            raise ValueError('IDs duplicados ou contagem diferente do manifesto')
        if any(c.get('status') != 'aprovado' or c.get('rascunho') is not False for c in chunks):
            raise ValueError('Somente chunks aprovados, sem rascunho, podem ser publicados')
        linhas = [{'chunk_id': c['chunk_id'], 'texto': c['texto'], 'metadados': metadados_chunk(c),
                   'embedding': vetor.tolist()} for c, vetor in zip(chunks, matriz)]
        # Uma transação publica o snapshot completo e seu manifesto; sem coleção parcial.
        self._requisitar('POST', 'rpc/fcte_rag_publicar',
                        json={'p_manifesto': manifesto, 'p_chunks': linhas})

    def preparar_snapshot(self, chunks: list[dict], vetores, manifesto: dict) -> None:
        """Disponibiliza uma versão sem trocar a coleção ativa dos deploys antigos."""
        from rag.armazenamento.embeddings import validar_vetores
        if manifesto['indice']['colecao'] != self.colecao:
            raise ValueError('Manifesto pertence a outra coleção')
        matriz = validar_vetores(vetores, len(chunks), 384)
        ids = {c['chunk_id'] for c in chunks}
        if not chunks or len(ids) != len(chunks) or len(chunks) != manifesto['indice']['total']:
            raise ValueError('IDs duplicados ou contagem diferente do manifesto')
        if any(c.get('status') != 'aprovado' or c.get('rascunho') is not False for c in chunks):
            raise ValueError('Somente chunks aprovados, sem rascunho, podem ser preparados')
        existentes = self._requisitar('GET', 'fcte_rag_colecoes', params={
            'colecao': 'eq.' + self.colecao, 'select': 'ativa,manifesto', 'limit': '1'}).json()
        if existentes and existentes[0]['manifesto'].get('assinatura') == manifesto['assinatura']:
            if self.ids() != ids or self.contar() != len(chunks):
                raise ValueError('Snapshot existente incompleto; publicação interrompida')
            return
        if existentes and (existentes[0]['ativa'] or existentes[0]['manifesto']):
            raise ValueError('Não é permitido sobrescrever outra versão publicada')
        linhas = [{'colecao': self.colecao, 'chunk_id': c['chunk_id'], 'texto': c['texto'],
                   'metadados': metadados_chunk(c), 'embedding': vetor.tolist()}
                  for c, vetor in zip(chunks, matriz)]
        # Manifesto vazio não é selecionável por nenhum corpus. Só liberar após conferir IDs.
        self._requisitar('POST', 'fcte_rag_colecoes', params={'on_conflict': 'colecao'},
                        headers={'Prefer': 'resolution=ignore-duplicates'},
                        json={'colecao': self.colecao, 'colecao_logica': manifesto['indice']['colecao_logica'],
                              'manifesto': {}, 'ativa': False})
        self._requisitar('POST', 'fcte_rag_chunks', params={'on_conflict': 'colecao,chunk_id'},
                        headers={'Prefer': 'resolution=merge-duplicates'}, json=linhas)
        if self.ids() != ids or self.contar() != len(chunks):
            raise ValueError('Snapshot incompleto; manifesto não publicado')
        resposta = self._requisitar('PATCH', 'fcte_rag_colecoes', params={
            'colecao': 'eq.' + self.colecao, 'ativa': 'eq.false'},
            headers={'Prefer': 'return=representation'}, json={'manifesto': manifesto})
        if len(resposta.json()) != 1:
            raise ValueError('Não foi possível concluir a preparação do snapshot')

    def consultar(self, vetor, limite: int, data: str) -> list[dict]:
        if limite <= 0:
            return []
        from rag.armazenamento.embeddings import validar_vetores
        matriz = validar_vetores([vetor], 1, 384)
        linhas = self._requisitar('POST', 'rpc/fcte_rag_buscar', json={
            'p_colecao': self.colecao, 'p_vetor': matriz[0].tolist(),
            'p_limite': limite, 'p_data': data}).json()
        return [dict(self._trecho(linha), distancia=float(linha['distancia'])) for linha in linhas]
