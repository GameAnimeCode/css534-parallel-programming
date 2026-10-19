#!/usr/bin/env python3
"""Drive the program 1 benchmarks on cssmpi from this repo.

Connection details come from .local/cssmpi.env (gitignored):
  USER_NAME, USER_PWD, USER_HOME_DIR, CLASS_HOME_DIR, SSH_PORT, SSH_ADDRESS
Their values are never printed: all remote output is masked first. Remote
paths must stay inside ~/prog1.

Usage (from anywhere):
  run_cssmpi.py push             copy src/*.cpp, variants and bench.py to ~/prog1, then build
  run_cssmpi.py start [phases]   start bench.py in the background (default: all)
  run_cssmpi.py status           last progress lines and RUNNING or IDLE
  run_cssmpi.py pull             copy ~/prog1/bench/results into bench/results
  run_cssmpi.py clean            delete ~/prog1/bench (keeps your sources and Tsp)
  run_cssmpi.py run '<command>'  run a command inside ~/prog1
  run_cssmpi.py put <local> <dest>   copy a file or folder to ~/prog1/<dest>
  run_cssmpi.py get <src> <local>    copy ~/prog1/<src> here
  run_cssmpi.py close            end the shared SSH connection
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# When ssh calls this script as SSH_ASKPASS, answer with the password and stop.
if os.environ.get("CSSMPI_ASKPASS_MODE"):
    print(os.environ["USER_PWD"])
    sys.exit(0)

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ENV_FILE = HERE.parents[2] / ".local" / "cssmpi.env"
REMOTE_DIR = "prog1"  # relative to the remote home directory
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
    return stream(["ssh", "-p", ENV["SSH_PORT"], *COMMON, TARGET, f"cd ~/{REMOTE_DIR} && {command}"])


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
    must(run("mkdir -p bench"))
    must(put(HERE / "bench.py", "bench/bench.py"))
    must(run("python3 bench/bench.py setup"))
    must(put(SRC / "EvalXOverMutate.cpp", "EvalXOverMutate.cpp"))
    must(put(SRC / "Tsp.cpp", "Tsp.cpp"))
    must(run("rm -rf bench/variants"))
    must(put(HERE / "build" / "variants", "bench/"))
    must(run("python3 bench/bench.py build"))


def start(phases):
    phases = " ".join(phases) or "all"
    # The parentheses keep the background job from holding the SSH session open:
    # without them, "cd ~/prog1 && job &" backgrounds the whole list, cd included.
    return run(f"(PROF_TSP=@CLASS_HOME@/prog1/Tsp nohup python3 bench/bench.py {phases} "
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
               "rm -rf bench && ls")
    return code


def close():
    subprocess.run(["ssh", "-p", ENV["SSH_PORT"], *COMMON, "-O", "exit", TARGET],
                   capture_output=True, env=PROC_ENV)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "push":
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
