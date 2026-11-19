#!/usr/bin/env python3
"""
Jalankan scheduler.py + bot.py bersamaan (untuk Railway Worker).

- scheduler.py : kirim ringkasan otomatis jam 07:00 & 19:30 WIB.
- bot.py       : jawab perintah /cek /xau /majors kapan saja.

Kalau salah satu mati, yang lain dimatikan juga dan proses ini keluar
dengan kode yang sama — Railway (restart ON_FAILURE) akan me-restart-nya.
"""
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    procs = {}
    for name in ("scheduler.py", "bot.py"):
        p = subprocess.Popen([sys.executable, str(BASE / name)], cwd=BASE)
        procs[name] = p
        print(f"[run] {name} mulai (pid {p.pid})", flush=True)
    try:
        while True:
            for name, p in procs.items():
                code = p.poll()
                if code is not None:
                    print(f"[run] {name} berhenti (exit {code}) — mematikan yang lain.",
                          flush=True)
                    for other in procs.values():
                        if other.poll() is None:
                            other.terminate()
                    sys.exit(code)
            time.sleep(5)
    except KeyboardInterrupt:
        print("[run] Berhenti.", flush=True)
        for p in procs.values():
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
