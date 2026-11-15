# Worker do gunicorn com limite de mensagens WebSocket ao nível do protocolo (8 KB): o servidor fecha com 1009
# antes de a app ler a mensagem.
from uvicorn.workers import UvicornWorker


class Worker(UvicornWorker):
    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "ws_max_size": 8192}
