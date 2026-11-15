# Endurecimento do processo do runner: torna-o "não despejável" (PR_SET_DUMPABLE=0).
# Efeito: os filhos (mesmo utilizador) não conseguem ler /proc/<pid>/environ nem fazer ptrace
# ao servidor ou aos irmãos, por isso o RUNNER_TOKEN e os nonces ficam protegidos.
import sys


def set_non_dumpable() -> bool:
    try:
        import ctypes
        ok = ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) == 0  # 4 = PR_SET_DUMPABLE
    except Exception:  # noqa: BLE001 - em sistemas sem prctl (macOS) segue sem isto
        return False
    for name in ("ctypes", "_ctypes"):  # o código do aluno não pode ver o ctypes já carregado
        sys.modules.pop(name, None)
    return ok
