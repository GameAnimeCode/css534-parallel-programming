#!/usr/bin/env python3
"""Benchmark runner for program 2. Runs on cssmpi from inside ~/prog2 (Python 3.9+)
in a login shell, so mpic++ and mpirun are the course's MPICH2 1.2.1p1.

Usage: python3 bench/bench.py <phase> [<phase> ...]
  setup     record machine info
  build     ./compile.sh for the code in src/, then one build per variant
  smoke     one quick run of each program (sanity check)
  verify    the handout's diff check, then more rank, thread and size combinations
  sequential  ./Wave2D 588 500 0, alternating with the professor's
  matrix    Wave2D_mpi 588 500 0 at ranks 1-6, threads 1-6, 8, 10
  noomp     the omp pragma removed, against the normal build at 1 thread
  reference this program and the professor's, alternating within each round
  phases    compute, exchange and init time per rank
  exchange  overlap against async and blocking exchanges
  all       every phase above except smoke, in order

Runs are sequential and round-robin across configurations. A run whose log
already contains "Elapsed time" is skipped, so a phase can be restarted. Phases
that need MPI share one mpd ring, which always comes down at the end.
"""
import csv
import filecmp
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
HOME = Path.home()
BENCH = ROOT / "bench"
RES = BENCH / "results"
LOGS = RES / "logs"
RUNS_CSV = RES / "runs.csv"
PHASES_CSV = RES / "phases.csv"
VERIFY_CSV = RES / "verify.csv"
RUN_FIELDS = ["experiment", "variant", "ranks", "threads", "rep", "elapsed_us", "load_max", "timestamp"]
PHASE_FIELDS = ["experiment", "variant", "ranks", "threads", "rep", "rank", "init", "compute",
                "exchange", "total"]
VERIFY_FIELDS = ["program", "ranks", "threads", "size", "max_time", "interval", "reference", "match"]
PROF_DIR = os.environ.get("PROF_DIR", "")
RING_NODES = 6
SIZE, MAX_TIME, INTERVAL = 588, 500, 0
TIMEOUT = 300
PHASES_LINE = re.compile(r"PHASES rank=(\d+) init=(\S+) compute=(\S+) exchange=(\S+) total=(\S+)\n?")
ELAPSED = re.compile(r"Elapsed time\s*=\s*(\d+)")


def progress(message):
    line = time.strftime("%H:%M:%S") + " " + message
    print(line, flush=True)
    with (RES / "progress.log").open("a") as f:
        f.write(line + "\n")


def append_row(path, fields, row):
    new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        if new:
            writer.writerow(fields)
        writer.writerow(row)


def binary_for(variant):
    if variant in ("src", "seq"):
        return str(ROOT / ("Wave2D_mpi" if variant == "src" else "Wave2D"))
    if variant == "prof":
        return f"{PROF_DIR}/Wave2D_mpi"
    if variant == "prof_seq":
        return f"{PROF_DIR}/Wave2D"
    return str(BENCH / "build" / variant / "Wave2D_mpi")


def mpirun(ranks, program, *args):
    return ["mpirun", "-np", str(ranks), program, *[str(a) for a in args]]


def capture(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          stdin=subprocess.DEVNULL, timeout=60).stdout


def ring_load():
    """Highest 1-minute load average across the six nodes."""
    text = capture(mpirun(RING_NODES, "/bin/cat", "/proc/loadavg"))
    return max(float(line.split()[0]) for line in text.splitlines() if line.strip())


def run_one(experiment, variant, ranks, threads, rep):
    log = LOGS / f"{experiment}_{variant}_n{ranks}_t{threads}_r{rep}.txt"
    if log.exists() and "Elapsed time" in log.read_text():
        return
    load = ring_load()
    stamp = int(time.time())
    if variant in ("seq", "prof_seq"):
        cmd = [binary_for(variant), SIZE, MAX_TIME, INTERVAL]
        cmd = [str(c) for c in cmd]
    else:
        cmd = mpirun(ranks, binary_for(variant), SIZE, MAX_TIME, INTERVAL, threads)
    with log.open("w") as out:
        try:
            subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           cwd=ROOT, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            out.write("timed out\n")
    text = log.read_text()
    if PROF_DIR and PROF_DIR in text:
        # Keep the class directory path out of the results.
        text = text.replace(PROF_DIR, "PROF_DIR")
        log.write_text(text)

    # Another rank's PHASES line can land inside rank 0's "Elapsed time" line,
    # so take those lines out first and let the number follow any whitespace.
    for match in PHASES_LINE.finditer(text):
        append_row(PHASES_CSV, PHASE_FIELDS, [experiment, variant, ranks, threads, rep, *match.groups()])
    found = ELAPSED.search(PHASES_LINE.sub("", text))
    elapsed = found.group(1) if found else ""
    append_row(RUNS_CSV, RUN_FIELDS, [experiment, variant, ranks, threads, rep, elapsed, load, stamp])
    progress(f"{experiment} {variant} n={ranks} t={threads} r={rep} {elapsed}us load={load}")


def sweep(experiment, reps, variants, ranks, threads):
    for rep in range(1, reps + 1):
        for n in ranks:
            for t in threads:
                for v in variants:
                    run_one(experiment, v, n, t, rep)


def ring_up():
    subprocess.run(["mpdallexit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    # CSSmpdboot leaves mpd running on our stdout, so it must write to a file,
    # never a pipe. Its output holds cluster addresses, so it stays out of results/.
    with (BENCH / "mpdboot.log").open("w") as out:
        subprocess.run(["CSSmpdboot", "-n", str(RING_NODES), "-v"], stdout=out, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, cwd=HOME, timeout=120)
    # A node can join the ring a moment after CSSmpdboot returns.
    for attempt in range(10):
        hosts = capture(mpirun(RING_NODES, "/bin/hostname")).split()
        if len(set(hosts)) == RING_NODES:
            break
        time.sleep(3)
    else:
        sys.exit(f"ring has {len(set(hosts))} distinct hosts, wanted {RING_NODES}")
    progress("ring up on " + " ".join(sorted(h.split(".")[0] for h in hosts)))


def ring_down():
    subprocess.run(["mpdallexit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


def phase_setup():
    cpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
    keep = ("Model name", "CPU(s):", "Thread(s) per core", "Core(s) per socket", "Socket(s)",
            "CPU max MHz", "L1d", "L2", "L3")
    lines = [f"date: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"]
    lines += [ln for ln in cpu.splitlines() if ln.startswith(keep)]
    lines.append(f"kernel: {os.uname().release}")
    gxx = subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    lines.append(f"compiler: {gxx}")
    version = subprocess.run(["mpich2version"], capture_output=True, text=True).stdout.splitlines()
    lines += [f"mpi: {ln.strip()}" for ln in version if "Version" in ln or "Device" in ln]
    lines.append(f"nproc: {os.cpu_count()}")
    (RES / "machine.txt").write_text("\n".join(lines) + "\n")
    progress("setup done")


def phase_build():
    if subprocess.run(["./compile.sh"], cwd=ROOT).returncode != 0:
        progress("compile.sh failed")
        sys.exit(1)
    for folder in sorted((BENCH / "variants").iterdir()):
        out = BENCH / "build" / folder.name
        out.mkdir(parents=True, exist_ok=True)
        # Same command and flags as compile.sh, with Timer files found in ~/prog2.
        step = ["mpic++", str(folder / "Wave2D_mpi.cpp"), str(ROOT / "Timer.cpp"), f"-I{ROOT}",
                "-fopenmp", "-o", "Wave2D_mpi"]
        if subprocess.run(step, cwd=out).returncode != 0:
            progress(f"build failed: {folder.name}")
            sys.exit(1)
    progress("build done")


def phase_smoke():
    run_one("smoke", "seq", 1, 1, 1)
    sweep("smoke", 1, ["src", "x_overlap", "x_async", "x_left", "x_right"], [6], [2])
    if PROF_DIR:
        run_one("smoke", "prof_seq", 1, 1, 1)
        run_one("smoke", "prof", 6, 2, 1)


def compare(out, reference, program, ranks, threads, size, max_time, interval, ref_name):
    match = filecmp.cmp(out, reference, shallow=False)
    append_row(VERIFY_CSV, VERIFY_FIELDS, [program, ranks, threads, size, max_time, interval, ref_name,
                                           "yes" if match else "no"])
    progress(f"verify {program} n={ranks} t={threads} {size} {max_time} {interval} vs {ref_name}: {match}")


def to_file(cmd, path):
    with path.open("w") as out:
        return subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                              cwd=ROOT, timeout=TIMEOUT).stderr


def phase_verify():
    """The handout's transcript first, under its own file names, then the wider checks."""
    session = []

    def shell(line, cmd, path):
        session.append(f"$ {line}")
        session.extend(to_file(cmd, path).splitlines())

    shell("./Wave2D 100 500 10 > out1.txt", ["./Wave2D", "100", "500", "10"], ROOT / "out1.txt")
    shell("mpirun -np 6 ./Wave2D_mpi 100 500 10 4 > out6.txt",
          mpirun(6, "./Wave2D_mpi", 100, 500, 10, 4), ROOT / "out6.txt")
    session.append("$ diff out1.txt out6.txt")
    session.extend(subprocess.run(["diff", "out1.txt", "out6.txt"], capture_output=True, text=True,
                                  cwd=ROOT).stdout.splitlines()[:5])
    (RES / "verify_session.txt").write_text("\n".join(session) + "\n")

    compare(ROOT / "out6.txt", ROOT / "out1.txt", "Wave2D_mpi", 6, 4, 100, 500, 10, "own Wave2D")
    if PROF_DIR:
        prof_out = Path(PROF_DIR) / "out1.txt"
        compare(ROOT / "out1.txt", prof_out, "Wave2D", 1, 1, 100, 500, 10, "professor out1.txt")
        compare(ROOT / "out6.txt", prof_out, "Wave2D_mpi", 6, 4, 100, 500, 10, "professor out1.txt")

    tmp = BENCH / "verify_tmp.txt"
    ref = BENCH / "verify_ref.txt"
    for n in range(1, 7):
        for t in (1, 2, 4):
            to_file(mpirun(n, "./Wave2D_mpi", 100, 500, 10, t), tmp)
            compare(tmp, ROOT / "out1.txt", "Wave2D_mpi", n, t, 100, 500, 10, "own Wave2D")

    # 233 does not divide evenly by any rank count above 1, and its weight is 2.
    size, steps, every = 233, 300, 7
    program = Path(PROF_DIR) / "Wave2D" if PROF_DIR else ROOT / "Wave2D"
    to_file([str(program), str(size), str(steps), str(every)], ref)
    name = "professor Wave2D" if PROF_DIR else "own Wave2D"
    to_file(["./Wave2D", str(size), str(steps), str(every)], tmp)
    compare(tmp, ref, "Wave2D", 1, 1, size, steps, every, name)
    for n in range(1, 7):
        to_file(mpirun(n, "./Wave2D_mpi", size, steps, every, 3), tmp)
        compare(tmp, ref, "Wave2D_mpi", n, 3, size, steps, every, name)

    for folder in sorted((BENCH / "build").iterdir()):
        to_file(mpirun(6, str(folder / "Wave2D_mpi"), 100, 500, 10, 2), tmp)
        compare(tmp, ROOT / "out1.txt", folder.name, 6, 2, 100, 500, 10, "own Wave2D")
    tmp.unlink()
    ref.unlink()


def phase_sequential():
    sweep("sequential", 10, ["seq", "prof_seq"] if PROF_DIR else ["seq"], [1], [1])


def phase_matrix():
    sweep("matrix", 10, ["src"], [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6, 8, 10])


def phase_reference():
    if not PROF_DIR:
        progress("reference skipped: PROF_DIR not set")
        return
    for rep in range(1, 11):
        for n, t in ((1, 1), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 10)):
            for variant in ("src", "prof"):
                run_one("reference", variant, n, t, rep)


def phase_noomp():
    """The omp pragma removed, against the normal build at one thread."""
    sweep("noomp", 5, ["no_omp", "src"], [1, 2, 3, 4, 5, 6], [1])
    tmp = BENCH / "verify_tmp.txt"
    to_file(mpirun(6, str(BENCH / "build" / "no_omp" / "Wave2D_mpi"), 100, 500, 10, 2), tmp)
    compare(tmp, ROOT / "out1.txt", "x_no_omp", 6, 2, 100, 500, 10, "own Wave2D")
    tmp.unlink()


def phase_phases():
    sweep("phases", 3, ["x_overlap"], [1, 2, 3, 4, 5, 6], [1, 2, 4, 5, 10])


def phase_exchange():
    sweep("exchange", 10, ["x_overlap", "x_async", "x_left", "x_right", "x_before"],
          [2, 4, 6], [1, 4])


PHASES = {name[len("phase_"):]: fn for name, fn in globals().items() if name.startswith("phase_")}
ALL = ["setup", "build", "verify", "sequential", "matrix", "noomp", "reference", "phases", "exchange"]
NO_RING = ("setup", "build")


def main(argv):
    if ROOT.name != "prog2":
        sys.exit("run from ~/prog2")
    if not argv or any(p not in PHASES and p != "all" for p in argv):
        sys.exit(__doc__)
    LOGS.mkdir(parents=True, exist_ok=True)
    lock = RES / ".lock"
    try:
        lock.mkdir()
    except FileExistsError:
        sys.exit("another bench.py is running")
    ring = False
    try:
        phases = [q for p in argv for q in (ALL if p == "all" else [p])]
        for p in phases:
            if p not in NO_RING and not ring:
                ring = True
                ring_up()
            progress(f"phase {p} start")
            PHASES[p]()
        progress("finished: " + " ".join(phases))
    finally:
        if ring:
            ring_down()
        shutil.rmtree(lock, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:])
