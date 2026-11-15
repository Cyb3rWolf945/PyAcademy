# Imagem do runner (contexto = ./runner). Só stdlib: sem dependências. Corre como "nobody".
# Stage "test": junta o pytest para correr os testes do runner dentro desta imagem.
FROM python:3.12-slim AS runner
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /runner
COPY *.py ./
USER 65534:65534
EXPOSE 9000
HEALTHCHECK --interval=10s --timeout=4s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9000/health', timeout=3).status==200 else 1)"]
CMD ["python", "-I", "/runner/server.py"]

FROM runner AS test
USER root
RUN pip install --no-cache-dir pytest==8.3.4
COPY tests ./tests
USER 65534:65534
CMD ["python", "-m", "pytest", "-q", "tests"]
