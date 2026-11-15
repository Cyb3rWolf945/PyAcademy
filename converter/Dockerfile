# Conversor de slides (só corre quando o professor importa um deck): LibreOffice headless + poppler-utils.
# Imagem fixa, sem rede (ver docker-compose.yml, perfil "tools"), utilizador não-root. Nunca faz parte do runtime dos alunos.
FROM python:3.12.8-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-impress poppler-utils fonts-liberation fonts-dejavu-core fonts-open-sans \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --create-home --uid 10001 converter \
    && mkdir -p /data/slides /input && chown converter:converter /data/slides
COPY convert.py /converter/convert.py
USER converter
WORKDIR /tmp
ENTRYPOINT ["python", "/converter/convert.py"]
