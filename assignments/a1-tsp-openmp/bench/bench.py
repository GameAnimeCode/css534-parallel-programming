#!/usr/bin/env python3
"""Benchmark runner for program 1. Runs on cssmpi from inside ~/prog1 (Python 3.9+)
and never writes outside it.

Usage: python3 bench/bench.py <phase> [<phase> ...]
  setup     record machine info
  build     ./compile.sh for the code in src/, then one build per variant
  smoke     one quick run of the src and profiled builds (sanity check)
  scaling   the code in src/, threads 1-10 (5 cores x 2 hyperthreads) and 12/16/20
  schedule  crossover schedule kinds and chunk sizes, plus static vs dynamic
  evaluate  evaluate static vs dynamic
  amdahl    only evaluate parallel, only crossover parallel, fully serial
  reference one run of the professor's binary (output check)
  phases    per-phase timing (evaluate loop, sort, crossover, mutate, ...)
  mutation  MUTATE_RATE 0, 10, 25, 50, 75, 100 at 5 threads (trip quality)
  all       every phase above except smoke, in order

Runs are sequential and round-robin across configurations. A run whose log
already contains "elapsed time" is skipped, so a phase can be restarted.
"""
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
RES = ROOT / "bench" / "results"
LOGS = RES / "logs"
RUNS_CSV = RES / "runs.csv"
PHASES_CSV = RES / "phases.csv"
RUN_FIELDS = ["experiment", "variant", "threads", "rep", "elapsed_us", "best_distance",
              "best_generation", "best_itinerary", "load1", "timestamp"]
PHASE_FIELDS = ["threads", "rep", "eval_loop_s", "sort_s", "select_s", "crossover_s",
                "mutate_s", "populate_s", "elapsed_us"]
PROF_TSP = os.environ.get("PROF_TSP", "")


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
    if variant == "src":
        return str(ROOT / "Tsp")
    if variant == "reference":
        return PROF_TSP
    return str(ROOT / "bench" / "build" / variant / "Tsp")


def run_one(experiment, variant, threads, rep):
    log = LOGS / f"{experiment}_{variant}_t{threads}_r{rep}.txt"
    if log.exists() and "elapsed time" in log.read_text():
        return
    load = Path("/proc/loadavg").read_text().split()[0]
    stamp = int(time.time())
    with log.open("w") as out:
        subprocess.run([binary_for(variant), str(threads)], stdout=out, stderr=subprocess.STDOUT, cwd=ROOT)
    text = log.read_text()
    if variant == "reference" and PROF_TSP in text:
        # Keep the class directory path out of the results.
        text = text.replace(PROF_TSP, "PROF_TSP")
        log.write_text(text)

    elapsed = dist = gen = itinerary = ""
    for line in text.splitlines():
        if line.startswith("elapsed time"):
            elapsed = line.split()[3]
        elif "shortest distance" in line:
            parts = line.split()
            gen, dist, itinerary = parts[1], parts[5], parts[-1]
    append_row(RUNS_CSV, RUN_FIELDS,
               [experiment, variant, threads, rep, elapsed, dist, gen, itinerary, load, stamp])

    if variant == "phases":
        for line in text.splitlines():
            if line.startswith("PHASES"):
                values = dict(kv.split("=", 1) for kv in line.split()[1:])
                append_row(PHASES_CSV, PHASE_FIELDS,
                           [values["threads"], rep, values["eval_loop"], values["sort"], values["select"],
                            values["crossover"], values["mutate"], values["populate"], elapsed])
    progress(f"{experiment} {variant} t={threads} r={rep} {elapsed}us best={dist} load={load}")


def sweep(experiment, reps, variants, threads):
    for rep in range(1, reps + 1):
        for t in threads:
            for v in variants:
                run_one(experiment, v, t, rep)


def phase_setup():
    cpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
    keep = ("Model name", "CPU(s):", "Thread(s) per core", "Core(s) per socket", "Socket(s)",
            "CPU max MHz", "L1d", "L2", "L3")
    lines = [f"date: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"]
    lines += [ln for ln in cpu.splitlines() if ln.startswith(keep)]
    lines.append(f"kernel: {os.uname().release}")
    gxx = subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    lines.append(f"compiler: {gxx}")
    lines.append(f"nproc: {os.cpu_count()}")
    (RES / "machine.txt").write_text("\n".join(lines) + "\n")
    progress("setup done")


def phase_build():
    if subprocess.run(["./compile.sh"], cwd=ROOT).returncode != 0:
        progress("compile.sh failed")
        sys.exit(1)
    for folder in sorted((ROOT / "bench" / "variants").iterdir()):
        out = ROOT / "bench" / "build" / folder.name
        out.mkdir(parents=True, exist_ok=True)
        tsp = folder / "Tsp.cpp" if (folder / "Tsp.cpp").exists() else ROOT / "Tsp.cpp"
        # Same commands and flags as compile.sh, only with Trip.h found in ~/prog1.
        steps = [
            ["g++", "-c", str(folder / "EvalXOverMutate.cpp"), f"-I{ROOT}", "-fopenmp", "-o", "EvalXOverMutate.o"],
            ["g++", str(tsp), str(ROOT / "Timer.o"), "EvalXOverMutate.o", f"-I{ROOT}", "-fopenmp", "-o", "Tsp"],
        ]
        for step in steps:
            if subprocess.run(step, cwd=out).returncode != 0:
                progress(f"build failed: {folder.name}")
                sys.exit(1)
    progress("build done")


def phase_smoke():
    sweep("smoke", 1, ["src", "phases"], [4])


def phase_scaling():
    sweep("scaling", 5, ["src"], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 20])


def phase_schedule():
    sweep("chunk", 3, ["xo_static", "xo_guided", "xo_dyn1", "xo_dyn8", "xo_dyn16",
                       "src", "xo_dyn256", "xo_dyn1024"], [5, 10])
    sweep("static_vs_dynamic", 3, ["xo_static", "src"], [1, 2, 4, 5, 8, 10])


def phase_evaluate():
    sweep("ev_schedule", 3, ["src", "ev_dyn64"], [1, 2, 4, 5, 8, 10])


def phase_amdahl():
    sweep("amdahl", 3, ["ev_only", "xo_only", "src"], [1, 2, 4, 5, 8, 10])
    sweep("serial", 5, ["serial", "src"], [1])


def phase_reference():
    if PROF_TSP and os.access(PROF_TSP, os.X_OK):
        sweep("reference", 1, ["reference"], [1, 4])
    else:
        progress("reference skipped: PROF_TSP not set")


def phase_phases():
    sweep("phases", 3, ["phases"], [1, 2, 4, 5, 8, 10])


def phase_mutation():
    sweep("mutation", 10, ["mutate0", "mutate10", "mutate25", "src", "mutate75", "mutate100"], [5])


PHASES = {name[len("phase_"):]: fn for name, fn in globals().items() if name.startswith("phase_")}
ALL = ["setup", "build", "scaling", "schedule", "evaluate", "amdahl", "reference", "phases", "mutation"]


def main(argv):
    if ROOT.name != "prog1":
        sys.exit("run from ~/prog1")
    if not argv or any(p not in PHASES and p != "all" for p in argv):
        sys.exit(__doc__)
    LOGS.mkdir(parents=True, exist_ok=True)
    lock = RES / ".lock"
    try:
        lock.mkdir()
    except FileExistsError:
        sys.exit("another bench.py is running")
    try:
        phases = [q for p in argv for q in (ALL if p == "all" else [p])]
        for p in phases:
            progress(f"phase {p} start")
            PHASES[p]()
        progress("finished: " + " ".join(phases))
    finally:
        shutil.rmtree(lock, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:])
