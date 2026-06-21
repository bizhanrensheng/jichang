import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "checkin_headless.log"
PID_FILE = ROOT / "checkin_headless.pid"


def run_foreground(extra_args: list[str]) -> int:
    import checkin

    old_argv = sys.argv[:]
    try:
        sys.argv = ["checkin.py", "--headless", "--slow", "0", *extra_args]
        return checkin.main()
    finally:
        sys.argv = old_argv


def start_background(extra_args: list[str]) -> int:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw if pythonw.exists() else Path(sys.executable))

    command = [
        executable,
        str(Path(__file__).resolve()),
        "--foreground",
        *extra_args,
    ]

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    with LOG_FILE.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )

    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"started background check-in, pid={process.pid}")
    print(f"log: {LOG_FILE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start check-in in the background")
    parser.add_argument("--foreground", action="store_true", help="run now and print logs here")
    args, extra_args = parser.parse_known_args()

    if args.foreground:
        return run_foreground(extra_args)
    return start_background(extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
