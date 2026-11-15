# Processo "zygote": arranca uma vez, já com o harness e a stdlib mais usada importados,
# e faz fork() por cada trabalho (poupa os ~30 ms de arrancar o Python).
# Protocolo (socket Unix com SCM_RIGHTS): [8 bytes de tamanho + 5 fds] + JSON -> responde pid e depois (estado, maxrss).
import gc
import os
import resource
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hardening  # noqa: E402

hardening.set_non_dumpable()
import fcntl  # noqa: E402
import harness  # noqa: E402,F401
import json  # noqa: E402

resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))
gc.collect()
gc.freeze()


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(min(1 << 20, n - len(buf)))
        if not chunk:
            raise EOFError
        buf += chunk
    return buf


def child(job, fds):
    try:
        os.setsid()
        high = [fcntl.fcntl(fd, fcntl.F_DUPFD, 100) for fd in fds]
        for target, src in enumerate(high):  # stdin, stdout, stderr, resultado(3), nonce(4)
            os.dup2(src, target)
        os.closerange(5, 1024)
        harness.child_main(job)
    finally:
        os._exit(70)


def main():
    sock = socket.socket(fileno=int(sys.argv[1]))
    while True:
        try:
            msg, fds, _, _ = socket.recv_fds(sock, 8, 5)
            if not msg:
                break
            if len(msg) < 8:
                msg += recv_exact(sock, 8 - len(msg))
            job = json.loads(recv_exact(sock, struct.unpack("!Q", msg)[0]))
        except (EOFError, OSError):
            break
        pid = os.fork()
        if pid == 0:
            sock.close()
            child(job, fds)
        for fd in fds:
            os.close(fd)
        sock.sendall(struct.pack("!i", pid))
        _, status, usage = os.wait4(pid, 0)
        sock.sendall(struct.pack("!iq", status, usage.ru_maxrss))


if __name__ == "__main__":
    main()
