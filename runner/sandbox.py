# Sandbox do runner (lado do PAI): lança o código do aluno num processo filho isolado e lê o resultado.
# Isolamento: ambiente vazio, cwd = pasta temporária nova (apagada no fim), rlimits (ver harness.apply_limits),
# novo grupo de processos (morto por inteiro no timeout), stdin/stdout/stderr com limites.
# Desempenho: pool de "zygotes" (python já arrancado) com fork por trabalho; se falhar, usa subprocess normal.
import json
import math
import os
import queue
import secrets
import selectors
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field

DIR = os.path.dirname(os.path.abspath(__file__))
STDOUT_CAP = 64 * 1024
STDERR_CAP = 16 * 1024
RESULT_CAP = 4 * 1024 * 1024
GENERATE_RESULT_CAP = 32 * 1024 * 1024
PY = [sys.executable, "-I", "-S"]


def default_concurrency() -> int:
    """RUNNER_CONCURRENCY, senão a quota de CPU do cgroup (compose `cpus`), senão os.cpu_count()."""
    if os.environ.get("RUNNER_CONCURRENCY"):
        return max(1, int(os.environ["RUNNER_CONCURRENCY"]))
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        return max(2, math.ceil(int(quota) / int(period)))
    except (OSError, ValueError):
        return max(2, os.cpu_count() or 2)


def reap_orphans(managed: set[int]) -> int:
    """Recolhe zombies que são nossos filhos mas não pertencem a ninguém (órfãos herdados quando somos o PID 1).
    Nunca toca nos pids geridos (zygotes e subprocessos de recurso), que têm dono a esperar por eles."""
    me, reaped = os.getpid(), 0
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) in managed:
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                rest = f.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if rest[0] == "Z" and int(rest[1]) == me:
            try:
                os.waitpid(int(name), os.WNOHANG)
                reaped += 1
            except ChildProcessError:
                pass
    return reaped


@dataclass
class CaseRun:
    status: str = "ok"  # ok | runtime_error | time_limit | memory_limit | output_limit
    stdout: str = ""
    stderr: str = ""
    value: object = None
    items: list | None = None  # modo gerar
    error: dict | None = None
    runtime_ms: int = 0
    peak_mem_kb: int = 0
    extra: dict = field(default_factory=dict)


class ZygoteError(Exception):
    pass


class Zygote:
    def __init__(self):
        self.sock, child = socket.socketpair()
        self.proc = subprocess.Popen(
            PY + [os.path.join(DIR, "zygote.py"), str(child.fileno())], env={}, pass_fds=[child.fileno()],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, close_fds=True,
        )
        child.close()
        self.dead = False

    def start(self, fds: list[int], payload: bytes) -> int:
        try:
            socket.send_fds(self.sock, [struct.pack("!Q", len(payload))], fds)
            self.sock.sendall(payload)
            return struct.unpack("!i", self._recv(4))[0]
        except (OSError, EOFError) as exc:
            self.dead = True
            raise ZygoteError(str(exc)) from exc

    def finish(self, timeout: float | None) -> tuple[int, int]:
        try:
            self.sock.settimeout(timeout)
            status, rss = struct.unpack("!iq", self._recv(12))
            return status, rss
        except socket.timeout:
            raise
        except (OSError, EOFError) as exc:
            self.dead = True
            raise ZygoteError(str(exc)) from exc
        finally:
            self.sock.settimeout(None)

    def _recv(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf

    def close(self):
        self.dead = True
        try:
            self.sock.close()
            self.proc.wait(timeout=2)
        except Exception:  # noqa: BLE001
            self.proc.kill()


def _kill_group(pid: int) -> None:
    for fn, target in ((os.killpg, pid), (os.kill, pid)):
        try:
            fn(target, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


class Sandbox:
    def __init__(self, size: int | None = None):
        self.size = size or default_concurrency()
        self._pool: queue.Queue = queue.Queue()
        self._zygotes: list[Zygote] = []
        self._fallback_pids: set[int] = set()
        for _ in range(self.size):
            self._pool.put(self._new_zygote())

    def _new_zygote(self):
        try:
            z = Zygote()
            self._zygotes.append(z)
            return z
        except OSError:
            return None  # None = slot sem zygote (usa subprocess normal)

    def managed_pids(self) -> set[int]:
        return {z.proc.pid for z in self._zygotes} | set(self._fallback_pids)

    def close(self):
        for z in self._zygotes:
            z.close()

    # -- API -----------------------------------------------------------------------------------------
    def run(self, job: dict, stdin: str = "") -> CaseRun:
        """Corre um trabalho num slot livre (bloqueia se todos estiverem ocupados = backpressure)."""
        slot = self._pool.get()
        try:
            return self._run(slot, job, stdin.encode("utf-8", "replace"))
        finally:
            if slot is not None and slot.dead:
                self._zygotes = [z for z in self._zygotes if z is not slot]
                slot.close()
                slot = self._new_zygote()
            self._pool.put(slot)

    def _run(self, slot, job: dict, stdin: bytes) -> CaseRun:
        cwd = tempfile.mkdtemp(prefix="run-")
        job = dict(job, cwd=cwd)
        fds: list[int] = []
        try:
            nonce = secrets.token_bytes(16)
            stdin_r, stdin_w = os.pipe()
            stdout_r, stdout_w = os.pipe()
            stderr_r, stderr_w = os.pipe()
            res_r, res_w = os.pipe()
            nonce_r, nonce_w = os.pipe()
            fds = [stdin_r, stdout_w, stderr_w, res_w, nonce_r]
            os.write(nonce_w, nonce)
            os.close(nonce_w)
            payload = json.dumps(job).encode()
            started = time.monotonic()
            handle = None
            if slot is not None and not slot.dead:
                try:
                    pid = slot.start(fds, payload)
                    handle = ("z", slot, pid)
                except ZygoteError:
                    handle = None
            if handle is None:
                handle = self._fallback(fds, payload, cwd)
            for fd in fds:
                os.close(fd)
            fds = []
            return self._collect(handle, job, nonce, stdin, stdin_w, stdout_r, stderr_r, res_r, started)
        finally:
            for fd in fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            shutil.rmtree(cwd, ignore_errors=True)

    def _fallback(self, fds, payload: bytes, cwd: str):
        stdin_r, stdout_w, stderr_w, res_w, nonce_r = fds
        pf = tempfile.TemporaryFile()  # anónimo: sem nome no disco
        pf.write(payload)
        pf.flush()
        pf.seek(0)
        code = f"import sys;sys.path.insert(0,{DIR!r});import hardening;hardening.set_non_dumpable();import harness;harness.fallback_main({res_w},{nonce_r},{pf.fileno()})"
        proc = subprocess.Popen(
            PY + ["-c", code], env={}, cwd=cwd, stdin=stdin_r, stdout=stdout_w, stderr=stderr_w,
            pass_fds=[res_w, nonce_r, pf.fileno()], start_new_session=True,
        )
        pf.close()
        self._fallback_pids.add(proc.pid)
        return ("p", proc, proc.pid)

    # -- leitura ---------------------------------------------------------------------------------------
    def _collect(self, handle, job, nonce, stdin, stdin_w, stdout_r, stderr_r, res_r, started) -> CaseRun:
        pid = handle[2]
        limit = float(job["limit_s"])
        deadline = started + limit + 0.1
        res_cap = GENERATE_RESULT_CAP if job["mode"] == "gerar" else RESULT_CAP
        sel = selectors.DefaultSelector()
        bufs = {"out": bytearray(), "err": bytearray(), "res": bytearray()}
        caps = {"out": STDOUT_CAP, "err": STDERR_CAP, "res": res_cap}
        readers = {stdout_r: "out", stderr_r: "err", res_r: "res"}
        for fd in readers:
            os.set_blocking(fd, False)
            sel.register(fd, selectors.EVENT_READ, "r")
        view, offset = memoryview(stdin), 0
        if stdin:
            os.set_blocking(stdin_w, False)
            sel.register(stdin_w, selectors.EVENT_WRITE, "w")
        else:
            os.close(stdin_w)
            stdin_w = None
        killed = None
        try:
            while readers and not killed:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    killed = "time"
                    break
                for key, _ in sel.select(min(remaining, 0.25)):
                    fd = key.fd
                    if key.data == "w":
                        try:
                            offset += os.write(fd, view[offset:offset + 65536])
                        except BlockingIOError:
                            continue
                        except OSError:
                            offset = len(stdin)
                        if offset >= len(stdin):
                            sel.unregister(fd)
                            os.close(fd)
                            stdin_w = None
                        continue
                    try:
                        data = os.read(fd, 65536)
                    except BlockingIOError:
                        continue
                    name = readers[fd]
                    if not data:
                        sel.unregister(fd)
                        del readers[fd]
                        continue
                    bufs[name] += data
                    if len(bufs[name]) > caps[name]:
                        killed = "output"
                        break
        finally:
            sel.close()
            for fd in {res_r, stdout_r, stderr_r} | ({stdin_w} if stdin_w is not None else set()):
                try:
                    os.close(fd)
                except OSError:
                    pass
        if killed:
            _kill_group(pid)
        try:
            status, rss = self._wait(handle, deadline, killed)
        finally:
            self._fallback_pids.discard(pid)
        elapsed = int((time.monotonic() - started) * 1000)
        return self._build(job, nonce, bufs, status, rss, elapsed, killed)

    def _wait(self, handle, deadline, killed):
        kind, obj, pid = handle
        timeout = None if killed else max(0.05, deadline - time.monotonic())
        try:
            if kind == "z":
                return obj.finish(timeout)
            if killed:
                return self._wait4(obj, pid)
            for _ in range(int(timeout / 0.01) + 1):  # espera curta: os pipes já fecharam
                done, status, rss = self._try_wait4(obj, pid)
                if done:
                    return status, rss
                time.sleep(0.01)
            raise socket.timeout
        except socket.timeout:
            _kill_group(pid)
            return self._wait(handle, deadline, "time_after")
        except ZygoteError:
            _kill_group(pid)
            return 0, 0

    @staticmethod
    def _try_wait4(proc, pid):  # noqa: D401
        done, status, usage = os.wait4(pid, os.WNOHANG)
        if done:
            proc.returncode = os.waitstatus_to_exitcode(status)
            return True, status, usage.ru_maxrss
        return False, 0, 0

    @staticmethod
    def _wait4(proc, pid):
        _, status, usage = os.wait4(pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
        return status, usage.ru_maxrss

    def _build(self, job, nonce, bufs, status, rss, elapsed, killed) -> CaseRun:
        run = CaseRun(runtime_ms=elapsed, peak_mem_kb=int(rss))
        run.stdout = bytes(bufs["out"][:STDOUT_CAP]).decode("utf-8", "replace")
        run.stderr = bytes(bufs["err"][:STDERR_CAP]).decode("utf-8", "replace")
        if killed == "time" or killed == "time_after":
            run.status = "time_limit"
            return run
        if killed == "output":
            run.status = "output_limit"
            return run
        res = bytes(bufs["res"])
        payload = None
        if res.startswith(nonce):  # o pai valida o nonce: o resto do que o aluno escrever é ignorado
            try:
                payload = json.loads(res[len(nonce):])
            except ValueError:
                payload = None
        sig = os.WTERMSIG(status) if os.WIFSIGNALED(status) else 0
        if payload is None:
            if sig in (signal.SIGXCPU,) or (sig == signal.SIGKILL and elapsed >= float(job["limit_s"]) * 900):
                run.status = "time_limit"
            elif sig == signal.SIGKILL:
                run.status = "memory_limit"
            else:
                name = signal.Signals(sig).name if sig else f"exit {os.WEXITSTATUS(status)}"
                run.status, run.error = "runtime_error", {"type": "Crash", "message": name, "line": None}
            return run
        if "error" in payload:
            run.error = payload["error"]
            run.status = "memory_limit" if run.error.get("type") == "MemoryError" else "runtime_error"
            return run
        run.value = payload.get("value")
        run.items = payload.get("items")
        return run
