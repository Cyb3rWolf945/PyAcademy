# Corre DENTRO do processo filho (um por caso de teste), antes e durante o código do aluno.
# Aplica os limites, bloqueia módulos perigosos, substitui input() (sem eco do prompt),
# executa o código e devolve o resultado por um pipe separado (fd 3) com um nonce por execução.
# A comparação com o esperado NUNCA acontece aqui: só no processo pai (compare.py).
import builtins
import copy
import io
import json
import math
import os
import resource
import sys
import sysconfig
import types

# Pré-carregados no zygote para o fork já vir "quente" (importar depois é instantâneo).
import bisect, collections, datetime, decimal, fractions, functools, heapq, itertools  # noqa: E401,F401
import operator, random, re, statistics, string, textwrap, time, typing  # noqa: E401,F401

STUDENT_FILE = "<aluno>"
RESULT_FD, NONCE_FD = 3, 4
MEM_BYTES = 256 * 1024 * 1024

# Camada extra (a principal é o contentor): módulos de sistema/rede/processos/introspeção do runtime.
BLOCKED = frozenset({
    "os", "posix", "nt", "subprocess", "_posixsubprocess", "socket", "_socket", "ssl", "ctypes", "_ctypes",
    "shutil", "multiprocessing", "threading", "_thread", "signal", "pty", "tty", "termios", "fcntl", "resource",
    "importlib", "runpy", "pkgutil", "zipimport", "mmap", "select", "selectors", "asyncio", "http", "urllib",
    "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "socketserver", "xmlrpc", "webbrowser", "sqlite3",
    "builtins", "gc", "marshal", "code", "codeop", "pdb", "faulthandler", "site", "sysconfig", "pwd", "grp",
    "syslog", "concurrent", "sched", "tempfile", "glob", "pathlib",
})
_OS_DENIED = (
    "system popen fork forkpty execl execle execlp execlpe execv execve execvp execvpe spawnl spawnle spawnlp "
    "spawnlpe spawnv spawnve spawnvp spawnvpe posix_spawn posix_spawnp kill killpg remove unlink rmdir removedirs "
    "rename renames replace mkdir makedirs symlink link chmod chown truncate setsid setuid setgid setgroups chroot"
).split()


def apply_limits(limit_s: float) -> None:
    """rlimits soft=hard (o aluno não os consegue subir). NPROC=1: sem novos processos/threads."""
    cpu = int(math.ceil(limit_s)) + 1
    for res, val in (
        (resource.RLIMIT_CPU, (cpu, cpu + 1)),
        (resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES)),
        (resource.RLIMIT_NPROC, (1, 1)),
        (resource.RLIMIT_NOFILE, (32, 32)),
        (resource.RLIMIT_FSIZE, (0, 0)),
        (resource.RLIMIT_CORE, (0, 0)),
    ):
        try:
            resource.setrlimit(res, val)
        except (ValueError, OSError):
            pass


def _install_guards() -> None:
    real_import = builtins.__import__
    stdlib = tuple(p + os.sep for p in {sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["platstdlib"]})

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if level == 0 and name.partition(".")[0] in BLOCKED:
            caller = sys._getframe(1).f_code.co_filename  # o ficheiro REAL de quem importa (não o __name__)
            if not (caller.startswith(stdlib) or caller.startswith("<frozen")):
                raise ImportError(f"import of '{name}' is not allowed")
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded

    def denied(*_a, **_k):
        raise PermissionError("operation not allowed")

    for mod in (os, sys.modules.get("posix")):
        for fname in _OS_DENIED:
            if mod is not None and hasattr(mod, fname):
                setattr(mod, fname, denied)


def _install_builtins() -> None:
    def input(prompt=""):  # noqa: A001 - o prompt é ignorado (não é escrito)
        line = sys.stdin.readline()
        if line == "":
            raise EOFError("EOF when reading a line")
        if line.endswith("\n"):
            line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
        return line

    def _exit(code=None):
        raise SystemExit(code)

    builtins.input = input
    builtins.exit = builtins.quit = _exit


def _describe(exc: BaseException) -> dict:
    line, tb = None, exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == STUDENT_FILE:
            line = tb.tb_lineno
        tb = tb.tb_next
    if isinstance(exc, SyntaxError) and exc.lineno:
        line = exc.lineno
    return {"type": type(exc).__name__, "message": str(exc)[:500], "line": line}


def _json_default(obj):
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=repr)
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    return {"__repr__": repr(obj)[:200]}


def _write_all(fd: int, data: bytes, write) -> None:
    view = memoryview(data)
    while view:
        n = write(fd, view)
        view = view[n:]


def _run(job: dict) -> dict:
    mode = job["mode"]
    main = types.ModuleType("__main__")
    main.__dict__["__builtins__"] = builtins
    if mode != "programa":
        main.__dict__["__name__"] = "aluno"  # evita correr o `if __name__ == "__main__"` do aluno
    sys.modules["__main__"] = main
    try:
        code = compile(job["code"], STUDENT_FILE, "exec")
        exec(code, main.__dict__)  # noqa: S102 - é o objetivo: corre no runner isolado
        if mode == "programa":
            return {"ok": True}
        fn = main.__dict__.get(job["fn"])
        if not callable(fn):
            return {"error": {"type": "NameError", "message": f"function '{job['fn']}' is not defined", "line": None}}
        value = fn(*copy.deepcopy(job["args"]))
        return {"ok": True, "value": json.loads(json.dumps(value, default=_json_default))}
    except SystemExit:
        return {"ok": True}
    except BaseException as exc:  # noqa: BLE001
        return {"error": _describe(exc)}


def _run_generate(job: dict) -> dict:
    """Modo 'gerar': corre a solução de referência e avalia cada gerador (código do autor, confiável)."""
    main = types.ModuleType("aluno")
    main.__dict__["__builtins__"] = builtins
    try:
        exec(compile(job["code"], STUDENT_FILE, "exec"), main.__dict__)  # noqa: S102
        fn = main.__dict__[job["fn"]]
        items = []
        for expr in job["exprs"]:
            args = eval(compile(expr, "<gerador>", "eval"), {"random": random, "math": math, "__builtins__": builtins})  # noqa: S307
            value = fn(*copy.deepcopy(args))
            items.append({"args": args, "devolve": value})
        return {"ok": True, "items": json.loads(json.dumps(items, default=_json_default))}
    except BaseException as exc:  # noqa: BLE001
        return {"error": _describe(exc)}


def child_main(job: dict, result_fd: int = RESULT_FD, nonce_fd: int = NONCE_FD) -> None:
    """Ponto de entrada do filho (já com stdin/stdout/stderr/pipes nos fds certos). Nunca regressa."""
    write = os.write  # guardado antes de o os ser "capado"
    exit_now = os._exit
    code = 0
    try:
        os.chdir(job["cwd"])
        apply_limits(job["limit_s"])
        nonce = b""
        while len(nonce) < 16:
            chunk = os.read(nonce_fd, 16 - len(nonce))
            if not chunk:
                break
            nonce += chunk
        os.close(nonce_fd)
        sys.stdin = io.open(0, "r", encoding="utf-8", errors="replace", closefd=False)
        sys.stdout = io.open(1, "w", encoding="utf-8", errors="replace", closefd=False)
        sys.stderr = io.open(2, "w", encoding="utf-8", errors="replace", closefd=False, buffering=1)
        sys.path[:] = [p for p in sys.path if p and not p.endswith("runner")]
        for name in ("harness", "zygote", "sandbox", "server", "compare", "evaluate"):
            sys.modules.pop(name, None)
        _install_guards()
        _install_builtins()
        result = _run_generate(job) if job["mode"] == "gerar" else _run(job)
        try:
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass
        try:
            _write_all(result_fd, nonce + json.dumps(result, default=_json_default).encode() + b"\n", write)
        except Exception:  # noqa: BLE001
            pass
    except BaseException:  # noqa: BLE001
        code = 70
    exit_now(code)


def fallback_main(result_fd: int, nonce_fd: int, payload_fd: int) -> None:
    """Alternativa sem zygote: `python -I -S` novo, com payload num fd herdado."""
    with os.fdopen(payload_fd, "rb") as f:
        job = json.loads(f.read())
    child_main(job, result_fd, nonce_fd)
