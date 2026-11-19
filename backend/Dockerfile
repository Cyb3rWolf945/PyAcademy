# Imagem da app PyArena (multi-stage). Contexto de build = raiz do projeto.
# Stage "css": compila o Tailwind v4 com o binário standalone (sem Node).
# Stage final: Python 3.12 slim, utilizador não-root, dependências fixadas por uv.lock.

# ---------- css ----------
FROM debian:bookworm-slim AS css
ARG TARGETARCH
ARG TAILWIND_VERSION=4.1.11
# sha256 oficiais da release v4.1.11 (sha256sums.txt)
ARG TW_SHA_ARM64=0409aa4222969f47fa6f4160fe5387e79bf7269e7afe0e8b22f7532c98e1d314
ARG TW_SHA_AMD64=64805b84af4292e043ea6f86d242f191c0ac75359c1a498455dfe6c642afdbab
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "$TARGETARCH" in \
      arm64) F=tailwindcss-linux-arm64; SHA="$TW_SHA_ARM64" ;; \
      amd64) F=tailwindcss-linux-x64;   SHA="$TW_SHA_AMD64" ;; \
      *) echo "arquitetura nao suportada: $TARGETARCH"; exit 1 ;; \
    esac; \
    curl -fsSL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/${F}"; \
    echo "${SHA}  /usr/local/bin/tailwindcss" | sha256sum -c -; \
    chmod +x /usr/local/bin/tailwindcss
WORKDIR /src
COPY frontend ./frontend
RUN tailwindcss -i frontend/styles/app.css -o frontend/dist/app.css --minify

# ---------- app ----------
FROM ghcr.io/astral-sh/uv:0.5.29 AS uv

FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend
COPY --from=uv /uv /usr/local/bin/uv
# poppler-utils: pdfinfo/pdftoppm para mostrar as páginas dos PDFs da "Leitura recomendada" como imagens
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
RUN useradd --system --create-home --uid 10001 pyarena
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY backend ./backend
COPY runner ./runner
COPY frontend ./frontend
COPY --from=css /src/frontend/dist ./frontend/dist
# Cache-busting: cada build põe o hash do CSS no link das páginas (app.css?v=<hash>),
# para nenhum browser ficar com estilos antigos depois de uma atualização.
RUN H=$(sha256sum frontend/dist/app.css | cut -c1-10) \
    && find frontend -name '*.html' -not -path 'frontend/dist/*' -exec sed -i "s#/dist/app.css\"#/dist/app.css?v=${H}\"#g" {} + \
    && mkdir -p /data/slides /data/docs && chown -R pyarena:pyarena /app /data/slides /data/docs
USER pyarena
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status==200 else 1)"
CMD ["sh", "/app/backend/serve.sh"]
