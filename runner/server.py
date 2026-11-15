# Servidor HTTP mínimo do runner (stdlib, sem dependências): POST /run, POST /generate, GET /health.
# Exige o cabeçalho X-Runner-Token (segredo partilhado com a app). Só é alcançável pela rede "sandbox".
import hmac
import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I não põe a pasta do script no path
import evaluate as ev  # noqa: E402
import hardening  # noqa: E402

hardening.set_non_dumpable()  # logo no arranque: o ambiente deste processo (RUNNER_TOKEN) fica ilegível aos filhos
from sandbox import Sandbox, reap_orphans  # noqa: E402

MAX_BODY = 32 * 1024 * 1024


def make_server(token: str, sandbox, host: str = "0.0.0.0", port: int = 9000) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def _send(self, status: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                return self._send(200, {"status": "ok", "slots": sandbox.size})
            self._send(404, {"error": "not_found"})

        def do_POST(self):  # noqa: N802
            if self.path not in ("/run", "/generate"):
                return self._send(404, {"error": "not_found"})
            if not hmac.compare_digest(self.headers.get("X-Runner-Token", ""), token):
                return self._send(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self._send(413, {"error": "too_large"})
                req = json.loads(self.rfile.read(length))
                result = (ev.evaluate if self.path == "/run" else ev.generate)(req, sandbox)
            except (ev.BadRequest, ValueError, KeyError, TypeError) as exc:
                return self._send(400, {"error": "bad_request", "detail": str(exc)[:200]})
            except Exception as exc:  # noqa: BLE001
                print("runner error:", repr(exc), file=sys.stderr, flush=True)
                return self._send(500, {"error": "internal"})
            self._send(200, result)

    ThreadingHTTPServer.request_queue_size = 256
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    token = os.environ.pop("RUNNER_TOKEN", "")
    if len(token) < 16:
        sys.exit("RUNNER_TOKEN em falta ou demasiado curto")
    sandbox = Sandbox()
    server = make_server(token, sandbox, port=int(os.environ.get("RUNNER_PORT", "9000")))
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())

    def reaper():  # somos o PID 1: recolhe os processos órfãos (zombies) que nos calhem
        while True:
            reap_orphans(sandbox.managed_pids())
            threading.Event().wait(2)

    threading.Thread(target=reaper, daemon=True).start()
    print(f"runner pronto: {sandbox.size} slots", flush=True)
    try:
        server.serve_forever()
    finally:
        sandbox.close()


if __name__ == "__main__":
    main()
