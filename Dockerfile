FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim
ARG RAG_PROFILE=light
ARG RAG_INDEX_BACKEND=supabase
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false RAG_WEB_DIR=/app/web PORT=8000 RAG_REQUIRE_AUTH=true \
    RAG_INDEX_BACKEND=${RAG_INDEX_BACKEND} RAG_PROFILE=${RAG_PROFILE}
WORKDIR /app/backend
RUN useradd --create-home --uid 1000 app
COPY backend/requirements.txt backend/requirements-api.txt ./
RUN if [ "$RAG_PROFILE" = "light" ]; then \
      pip install -r requirements-api.txt; \
    elif [ "$RAG_PROFILE" = "full" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libgomp1 \
      && rm -rf /var/lib/apt/lists/* \
      && pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
      && pip install -r requirements.txt; \
    else echo "RAG_PROFILE deve ser light ou full" >&2; exit 1; fi
COPY backend/rag ./rag
COPY backend/config ./config
COPY backend/scripts ./scripts
COPY backend/data/catalogo ./data/catalogo
COPY backend/data/chunks ./data/chunks
COPY backend/avaliacao/resultados/semana3-llm-rag-20261112-v1/metricas.json backend/avaliacao/resultados/semana3-llm-rag-20261112-v1/gabarito.json backend/avaliacao/resultados/semana3-llm-rag-20261112-v1/configuracao.json ./avaliacao/resultados/semana3-llm-rag-20261112-v1/
# Light não baixa modelos; full preserva o pipeline com E5 e reranker.
# Nenhum perfil acessa Supabase ou Gemini durante o build.
RUN if [ "$RAG_PROFILE" = "full" ]; then \
      python scripts/preparar_modelos.py --incluir-e5 \
      && if [ "$RAG_INDEX_BACKEND" = "chroma" ]; then \
           python scripts/05_indexar.py && python scripts/06_conferir.py; \
         fi; \
    else python -c "from rag.config import carregar_config; from rag.consulta.servico import ServicoRAG; assert carregar_config()['perfil'] == 'light'"; fi
COPY --from=frontend /web/dist /app/web
RUN mkdir -p data/execucoes && chown -R app:app /app
USER app
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn rag.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
