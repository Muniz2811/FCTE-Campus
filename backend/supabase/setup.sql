-- Execute integralmente no SQL Editor do projeto Supabase.
-- Objetos exclusivos do RAG: não modifica tabelas/buckets da coleta.
begin;
create schema if not exists extensions;
create extension if not exists vector with schema extensions;
grant usage on schema public, extensions to service_role;

create table if not exists public.fcte_rag_colecoes (
  colecao text primary key,
  colecao_logica text not null,
  manifesto jsonb not null,
  ativa boolean not null default false,
  publicado_em timestamptz not null default now()
);
create unique index if not exists fcte_rag_base_ativa
  on public.fcte_rag_colecoes (colecao_logica) where ativa;

create table if not exists public.fcte_rag_chunks (
  colecao text not null references public.fcte_rag_colecoes(colecao),
  chunk_id text not null,
  texto text not null check (length(texto) > 0),
  metadados jsonb not null,
  embedding extensions.vector(384) not null,
  primary key (colecao, chunk_id),
  check (metadados->>'status' = 'aprovado'),
  check (metadados->>'rascunho' = 'false')
);

alter table public.fcte_rag_colecoes enable row level security;
alter table public.fcte_rag_chunks enable row level security;
revoke all on public.fcte_rag_colecoes, public.fcte_rag_chunks from public, anon, authenticated;
grant select, insert, update, delete on public.fcte_rag_colecoes, public.fcte_rag_chunks to service_role;

-- Snapshot inteiro em uma transação: falha de validação deixa a base anterior ativa.
create or replace function public.fcte_rag_publicar(p_manifesto jsonb, p_chunks jsonb)
returns integer
language plpgsql security invoker set search_path = ''
as $$
declare
  nome text := p_manifesto->'indice'->>'colecao';
  logica text := p_manifesto->'indice'->>'colecao_logica';
  assinatura text := p_manifesto->>'assinatura';
  quantidade integer;
begin
  if jsonb_typeof(p_chunks) is distinct from 'array' then
    raise exception 'chunks deve ser um array';
  end if;
  quantidade := jsonb_array_length(p_chunks);
  if quantidade < 1 or quantidade > 1000 then
    raise exception 'Este protótipo publica entre 1 e 1000 chunks por coleção';
  end if;
  if logica is null or assinatura is null or assinatura !~ '^[0-9a-f]{64}$'
     or nome is distinct from (logica || '-' || left(assinatura, 20))
     or (p_manifesto->'embeddings'->>'dimensao')::integer is distinct from 384
     or p_manifesto->'indice'->>'distancia' is distinct from 'cosine'
     or (p_manifesto->'indice'->>'total')::integer is distinct from quantidade then
    raise exception 'Manifesto incompatível com pgvector/E5 de 384 dimensões';
  end if;
  if exists (
    select 1 from jsonb_array_elements(p_chunks) c
    where nullif(c->>'chunk_id', '') is null or nullif(c->>'texto', '') is null
      or c->'metadados'->>'status' is distinct from 'aprovado'
      or c->'metadados'->>'rascunho' is distinct from 'false'
      or jsonb_array_length(c->'embedding') is distinct from 384
      or c->'metadados'->>'validade_ord' is null
  ) then
    raise exception 'Chunk inválido, não aprovado ou com embedding incompatível';
  end if;
  if (select count(distinct c->>'chunk_id') from jsonb_array_elements(p_chunks) c) <> quantidade then
    raise exception 'chunk_id duplicado';
  end if;

  -- Serializa publicações concorrentes da mesma base lógica.
  perform pg_advisory_xact_lock(hashtextextended(logica, 0));
  update public.fcte_rag_colecoes set ativa = false where colecao_logica = logica;
  insert into public.fcte_rag_colecoes (colecao, colecao_logica, manifesto, ativa)
  values (nome, logica, p_manifesto, true)
  on conflict (colecao) do update set manifesto = excluded.manifesto,
    ativa = true, publicado_em = now();
  -- Somente esta versão é substituída; coleções antigas permanecem preservadas.
  delete from public.fcte_rag_chunks where colecao = nome;
  insert into public.fcte_rag_chunks (colecao, chunk_id, texto, metadados, embedding)
  select nome, c->>'chunk_id', c->>'texto', c->'metadados',
         (c->'embedding')::text::extensions.vector(384)
  from jsonb_array_elements(p_chunks) c;
  return quantidade;
end;
$$;

-- Busca exata por cosseno: suficiente para os 174 chunks atuais.
-- Não criamos HNSW aqui para não introduzir aproximação na migração/avaliação.
create or replace function public.fcte_rag_buscar(
  p_colecao text, p_vetor extensions.vector(384), p_limite integer, p_data date
)
returns table (chunk_id text, texto text, metadados jsonb, distancia double precision)
language sql stable security invoker set search_path = ''
as $$
  select c.chunk_id, c.texto, c.metadados,
         c.embedding operator(extensions.<=>) p_vetor as distancia
  from public.fcte_rag_chunks c
  where c.colecao = p_colecao
    and c.metadados->>'status' = 'aprovado'
    and c.metadados->>'rascunho' = 'false'
    and c.metadados->>'abrangencia' in ('Gama', 'UnB geral', 'DF')
    and (c.metadados->>'validade_ord')::integer >= to_char(p_data, 'YYYYMMDD')::integer
  order by c.embedding operator(extensions.<=>) p_vetor, c.chunk_id
  limit least(greatest(p_limite, 0), 1000);
$$;

revoke all on function public.fcte_rag_publicar(jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.fcte_rag_buscar(text, extensions.vector, integer, date) from public, anon, authenticated;
grant execute on function public.fcte_rag_publicar(jsonb, jsonb) to service_role;
grant execute on function public.fcte_rag_buscar(text, extensions.vector, integer, date) to service_role;
notify pgrst, 'reload schema';
commit;
