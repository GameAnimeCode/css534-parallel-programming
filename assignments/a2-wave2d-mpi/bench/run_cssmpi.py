#!/usr/bin/env python3
"""Drive the program 2 benchmarks on cssmpi from this repo.

Connection details come from .local/cssmpi.env (gitignored):
  USER_NAME, USER_PWD, USER_HOME_DIR, CLASS_HOME_DIR, SSH_PORT, SSH_ADDRESS
Their values are never printed: all remote output is masked first. Remote
paths must stay inside ~/prog2.

Usage (from anywhere):
  run_cssmpi.py all              push, start, wait, pull, summarize, figures, clean
  run_cssmpi.py push             copy src/*.cpp, variants and bench.py to ~/prog2, then build
  run_cssmpi.py start [phases]   start bench.py in the background (default: all)
  run_cssmpi.py status           last progress lines and RUNNING or IDLE
  run_cssmpi.py pull             copy ~/prog2/bench/results into bench/results
  run_cssmpi.py clean            delete ~/prog2/bench (keeps sources, binaries, out1.txt, out6.txt)
  run_cssmpi.py run '<command>'  run a command inside ~/prog2 in a login shell
  run_cssmpi.py put <local> <dest>   copy a file or folder to ~/prog2/<dest>
  run_cssmpi.py get <src> <local>    copy ~/prog2/<src> here
  run_cssmpi.py close            end the shared SSH connection
"""
import os
import subprocess
import shlex
import sys
import tempfile
import time
from pathlib import Path

# When ssh calls this script as SSH_ASKPASS, answer with the password and stop.
if os.environ.get("CSSMPI_ASKPASS_MODE"):
    print(os.environ["USER_PWD"])
    sys.exit(0)

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ENV_FILE = HERE.parents[2] / ".local" / "cssmpi.env"
REMOTE_DIR = "prog2"  # relative to the remote home directory
KEYS = ["USER_NAME", "USER_PWD", "USER_HOME_DIR", "CLASS_HOME_DIR", "SSH_PORT", "SSH_ADDRESS"]
MASKS = {"USER_PWD": "<pwd>", "CLASS_HOME_DIR": "<class_home>", "USER_HOME_DIR": "<home>",
         "SSH_ADDRESS": "<host>", "USER_NAME": "<user>"}


def load_env():
    """Source the env file with bash, exactly as a shell would, and keep our keys."""
    if not ENV_FILE.exists():
        sys.exit("error: .local/cssmpi.env not found")
    dump = subprocess.run(["bash", "-c", 'set -a; source "$1"; env -0', "_", str(ENV_FILE)],
                          capture_output=True, check=True).stdout.decode()
    values = dict(item.split("=", 1) for item in dump.split("\0") if "=" in item)
    missing = [k for k in KEYS if not values.get(k)]
    if missing:
        sys.exit(f"error: missing in cssmpi.env: {', '.join(missing)}")
    return {k: values[k] for k in KEYS}


ENV = load_env()
CONTROL = str(Path(tempfile.gettempdir()) / "cssmpi-ctl-%C")
TARGET = f"{ENV['USER_NAME']}@{ENV['SSH_ADDRESS']}"
COMMON = ["-o", "StrictHostKeyChecking=accept-new", "-o", f"ControlPath={CONTROL}"]
PROC_ENV = {**os.environ, **ENV, "SSH_ASKPASS": str(Path(__file__).resolve()),
            "SSH_ASKPASS_REQUIRE": "force", "CSSMPI_ASKPASS_MODE": "1"}


def mask(text):
    for key in sorted(MASKS, key=lambda k: -len(ENV[k])):
        text = text.replace(ENV[key], MASKS[key])
    return text


def check_rel(path):
    if path.startswith(("/", "~")) or ".." in path:
        sys.exit(f"error: remote path must stay inside ~/{REMOTE_DIR}: {path}")


def ensure_master():
    """Open the shared connection once, detached, so no later call waits on it."""
    check = subprocess.run(["ssh", "-p", ENV["SSH_PORT"], *COMMON, "-O", "check", TARGET],
                           capture_output=True, env=PROC_ENV)
    if check.returncode == 0:
        return
    subprocess.run(["ssh", "-p", ENV["SSH_PORT"], *COMMON, "-o", "ControlMaster=yes",
                    "-o", "ControlPersist=30m", "-o", "PreferredAuthentications=keyboard-interactive,password",
                    "-f", "-N", TARGET],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env=PROC_ENV, check=True)


def stream(cmd):
    """Run a local command and print its output line by line, masked."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=PROC_ENV,
                            stdin=subprocess.DEVNULL, text=True)
    for line in proc.stdout:
        print(mask(line), end="", flush=True)
    return proc.wait()


def run(command):
    ensure_master()
    # @CLASS_HOME@ expands to CLASS_HOME_DIR here, so callers never see the value.
    command = command.replace("@CLASS_HOME@", ENV["CLASS_HOME_DIR"])
    # A login shell is what puts MPICH2 1.2.1p1 ahead of the system's MPICH 5.
    remote = f"cd ~/{REMOTE_DIR} && {command}"
    return stream(["ssh", "-p", ENV["SSH_PORT"], *COMMON, TARGET, f"bash -lc {shlex.quote(remote)}"])


def put(local, dest):
    check_rel(dest)
    ensure_master()
    return stream(["scp", "-q", "-r", "-P", ENV["SSH_PORT"], *COMMON, str(local), f"{TARGET}:{REMOTE_DIR}/{dest}"])


def get(src, local):
    check_rel(src)
    ensure_master()
    return stream(["scp", "-q", "-r", "-P", ENV["SSH_PORT"], *COMMON, f"{TARGET}:{REMOTE_DIR}/{src}", str(local)])


def must(code):
    if code != 0:
        sys.exit(code)


def push():
    must(subprocess.run([sys.executable, str(HERE / "make_variants.py")]).returncode)
    must(run("mkdir -p bench/results"))
    must(put(HERE / "bench.py", "bench/bench.py"))
    must(run("python3 bench/bench.py setup"))
    must(put(SRC / "Wave2D.cpp", "Wave2D.cpp"))
    must(put(SRC / "Wave2D_mpi.cpp", "Wave2D_mpi.cpp"))
    must(run("rm -rf bench/variants"))
    must(put(HERE / "build" / "variants", "bench/"))
    must(run("python3 bench/bench.py build"))


def start(phases):
    phases = " ".join(phases) or "all"
    # The parentheses keep the background job from holding the SSH session open:
    # without them, "cd ~/prog2 && job &" backgrounds the whole list, cd included.
    return run(f"(PROF_DIR=@CLASS_HOME@/prog2 nohup python3 bench/bench.py {phases} "
               f"> bench/results/nohup.log 2>&1 < /dev/null &); echo started: {phases}")


def status():
    return run("tail -n 8 bench/results/progress.log; "
               "if [ -d bench/results/.lock ]; then echo STATE: RUNNING; else echo STATE: IDLE; fi")


def pull():
    must(get("bench/results", HERE))
    lock = HERE / "results" / ".lock"
    if lock.exists():
        lock.rmdir()
    print("pulled into bench/results")


def clean():
    code = run("if [ -d bench/results/.lock ]; then echo 'benchmark still running, not cleaning'; exit 1; fi; "
               "mpdallexit 2>/dev/null; rm -rf bench && ls")
    return code


def run_all():
    """The whole suite, unattended. Stops before cleaning if the run did not finish."""
    push()
    must(start([]))
    time.sleep(10)
    while True:
        time.sleep(60)
        ensure_master()
        state = subprocess.run(["ssh", "-p", ENV["SSH_PORT"], *COMMON, TARGET,
                                f"tail -n 1 {REMOTE_DIR}/bench/results/progress.log; "
                                f"test -d {REMOTE_DIR}/bench/results/.lock"],
                               capture_output=True, text=True, env=PROC_ENV)
        print(mask(state.stdout), end="", flush=True)
        if state.returncode != 0:
            break
    pull()
    if "finished:" not in (HERE / "results" / "progress.log").read_text().splitlines()[-1]:
        sys.exit("run did not finish: see bench/results/nohup.log; ~/prog2/bench was left in place")
    must(subprocess.run([sys.executable, str(HERE / "summarize.py")]).returncode)
    must(subprocess.run([sys.executable, str(HERE / "make_figures.py")]).returncode)
    must(clean())


def close():
    subprocess.run(["ssh", "-p", ENV["SSH_PORT"], *COMMON, "-O", "exit", TARGET],
                   capture_output=True, env=PROC_ENV)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "all":
        run_all()
    elif cmd == "push":
        push()
    elif cmd == "start":
        must(start(rest))
    elif cmd == "status":
        must(status())
    elif cmd == "pull":
        pull()
    elif cmd == "clean":
        must(clean())
    elif cmd == "run" and len(rest) == 1:
        must(run(rest[0]))
    elif cmd == "put" and len(rest) == 2:
        must(put(rest[0], rest[1]))
    elif cmd == "get" and len(rest) == 2:
        must(get(rest[0], rest[1]))
    elif cmd == "close":
        close()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
