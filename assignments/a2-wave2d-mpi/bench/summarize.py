#!/usr/bin/env python3
"""Summarize the CSSMPI benchmark results for the writeup.

Reads results/runs.csv, results/phases.csv, results/verify.csv and the
professor's timings in ../src/measurements2025.txt, then writes
  results/summary/*.csv   small tables that the pgfplots charts read
  results/tables/*.md     Markdown tables that writeup.qmd includes
Run it after pulling new results: python3 bench/summarize.py
"""
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SUMMARY = RES / "summary"
TABLES = RES / "tables"
HANDOUT = HERE.parent / "src" / "measurements2025.txt"

RANKS = [1, 2, 3, 4, 5, 6]
# 10 threads stay in runs.csv but out of the report: another job held a CPU on rank 0's node.
THREADS = [1, 2, 3, 4, 5, 6, 8]
TARGET_MPI = 2.35      # handout: 2.161763 / 0.921633
TARGET_HYBRID = 4.81   # handout: 2.161763 / 0.440657
HANDOUT_BASE = 2.161763

EXCHANGE = [("x_overlap", "Overlap"), ("x_async", "Async only"), ("x_left", "Blocking, left first"),
            ("x_right", "Blocking, right first"), ("x_before", "Before compute")]


def load_runs():
    rows = list(csv.DictReader((RES / "runs.csv").open()))
    for r in rows:
        r["ranks"], r["threads"] = int(r["ranks"]), int(r["threads"])
        r["load"] = float(r["load_max"])
        r["ok"] = bool(r["elapsed_us"])  # empty when the program failed
        r["sec"] = int(r["elapsed_us"]) / 1e6 if r["ok"] else float("nan")
    return rows


def group(rows, experiment):
    """Map (variant, ranks, threads) to the elapsed seconds of one experiment."""
    out = defaultdict(list)
    for r in rows:
        if r["experiment"] == experiment and r["ok"]:
            out[(r["variant"], r["ranks"], r["threads"])].append(r["sec"])
    return out


def median(values):
    """Timings use the median, so one run hit by someone else's job does not move a result."""
    return statistics.median(values) if values else float("nan")


def mean(values):
    return statistics.fmean(values) if values else float("nan")


def write_csv(name, header, rows):
    SUMMARY.mkdir(parents=True, exist_ok=True)
    with (SUMMARY / name).open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_table(name, header, rows, caption, label, align=None):
    TABLES.mkdir(parents=True, exist_ok=True)
    align = align or ["r"] * len(header)
    # Compact rows: Pandoc lets a pipe table keep its natural column widths (no
    # wrapped headers) only while every source line stays within 72 characters.
    sep = ["--:" if a == "r" else ":--" if a == "l" else ":-:" for a in align]
    lines = ["|" + "|".join(header) + "|", "|" + "|".join(sep) + "|"]
    lines += ["|" + "|".join(str(c) for c in row) + "|" for row in rows]
    too_long = [ln for ln in lines if len(ln) > 72]
    if too_long:
        print(f"warning: {name} has lines over 72 characters; Pandoc will wrap its columns")
    lines += ["", f": {caption} {{#{label}}}", ""]
    (TABLES / name).write_text("\n".join(lines))


def handout_times():
    """The professor's 588 500 0 timings by (ranks, threads) from the handout."""
    text = HANDOUT.read_text()
    found = re.findall(r"mpirun -np (\d) \./Wave2D_mpi 588 500 0 (\d)\n(?:rank.*\n)+Elapsed time = (\d+)", text)
    return {(int(n), int(t)): int(us) / 1e6 for n, t, us in found}


def matrix(rows):
    g = group(rows, "matrix")
    base = median(g[("src", 1, 1)])
    time_rows, mean_rows, speed_rows, csv_time, csv_speed = [], [], [], [], []
    for n in RANKS:
        ms = [median(g[("src", n, t)]) for t in THREADS]
        time_rows.append([n] + [f"{m:.2f}" for m in ms])
        mean_rows.append([n] + [f"{mean(g[('src', n, t)]):.2f}" for t in THREADS])
        speed_rows.append([n] + [f"{base / m:.2f}" for m in ms])
        csv_time.append([n] + [f"{m:.3f}" for m in ms])
        csv_speed.append([n] + [f"{base / m:.3f}" for m in ms])
    head = [" "] + [f"{t}" for t in THREADS]
    names = ["ranks"] + [f"t{t}" for t in THREADS]
    write_csv("matrix.csv", names, csv_time)
    write_csv("speedup.csv", names, csv_speed)
    write_table("matrix.md", head, time_rows,
                "Median time (s), 10 runs each. Rows are ranks, columns are threads.", "tbl-matrix")
    write_table("matrix_mean.md", head, mean_rows,
                "Mean time (s), same runs. Rows are ranks, columns are threads.", "tbl-matrix-mean")
    write_table("speedup.md", head, speed_rows,
                "Speedup over 1 rank, 1 thread. Rows are ranks, columns are threads.", "tbl-speedup")
    spreads = [100 * (max(s) - min(s)) / min(s) for k, s in g.items() if k[2] in THREADS]
    return g, base, spreads


def requirements(g, base, seq):
    hand = handout_times()
    n1 = median(g[("src", 6, 1)])
    best_t = min(THREADS, key=lambda t: median(g[("src", 6, t)]))
    in_range = min((1, 2, 3, 4), key=lambda t: median(g[("src", 6, t)]))
    rows = []
    for label, t, target in (("6 ranks, 1 thread", 1, TARGET_MPI), (f"6 ranks, {in_range} threads", in_range, TARGET_HYBRID),
                             (f"6 ranks, {best_t} threads", best_t, TARGET_HYBRID)):
        m = median(g[("src", 6, t)])
        rows.append([label, f"{m:.3f}", f"{mean(g[('src', 6, t)]):.3f}", f"{target}", f"{base / m:.2f}", f"{HANDOUT_BASE / m:.2f}", f"{seq / m:.2f}"])
    write_table("requirements.md", ["Run", "Median (s)", "Mean (s)", "Target", "Own", "Handout", "Wave2D"], rows,
                "Speedup against the targets, from the medians.",
                "tbl-requirements", ["l", "r", "r", "r", "r", "r", "r"])
    return {"best_threads": best_t, "in_range_threads": in_range, "n1": n1, "hand": hand}


def change(rows, base):
    """The blocking exchange against the overlap for the two requirements, from the same rounds."""
    g = group(rows, "exchange")
    md_rows = []
    for label, t, target in (("6 ranks, 1 thread", 1, TARGET_MPI), ("6 ranks, 4 threads", 4, TARGET_HYBRID)):
        before, after = median(g[("x_left", 6, t)]), median(g[("x_overlap", 6, t)])
        md_rows.append([label, target, f"{before:.3f}", f"{after:.3f}", f"{base / before:.2f}", f"{base / after:.2f}",
                        f"{HANDOUT_BASE / after:.2f}"])
    write_table("change.md", ["Run", "Target", "Before (s)", "After (s)", "Own before", "Own after", "Handout"],
                md_rows, "Blocking exchange against the overlap, 10 runs each.", "tbl-change",
                ["l", "r", "r", "r", "r", "r", "r"])


def reference(rows, seq, pseq):
    prof = group(rows, "reference")
    hand = handout_times()
    md_rows = []
    seq_runs = group(rows, "sequential")
    md_rows.append(["`Wave2D`", "n/a", f"{pseq:.2f}", f"{mean(seq_runs[('prof_seq', 1, 1)]):.2f}",
                    f"{seq:.2f}", f"{mean(seq_runs[('seq', 1, 1)]):.2f}"])
    for n, t in ((1, 1), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5)):
        h = hand.get((n, t))
        label = "1 rank, 1 thread" if n == 1 else f"6 ranks, {t} thread{'s' if t > 1 else ''}"
        md_rows.append([label,
                        f"{h:.2f}" if h else "n/a", f"{median(prof[('prof', n, t)]):.2f}", f"{mean(prof[('prof', n, t)]):.2f}",
                        f"{median(prof[('src', n, t)]):.2f}", f"{mean(prof[('src', n, t)]):.2f}"])
    write_table("reference.md", ["Run", "Handout", "Prof. med.", "Prof. mean", "My med.", "My mean"], md_rows,
                "Time (s) against the professor's binaries, 10 runs each.", "tbl-reference", ["l", "r", "r", "r", "r", "r"])


def noomp(rows):
    g = group(rows, "noomp")
    md_rows = []
    for n in RANKS:
        off, on = median(g[("no_omp", n, 1)]), median(g[("src", n, 1)])
        md_rows.append([n, f"{off:.3f}", f"{on:.3f}", f"{100 * (on - off) / off:+.1f}%"])
    write_table("noomp.md", ["Ranks", "No OpenMP (s)", "OpenMP, 1 thread (s)", "Change"], md_rows,
                "OpenMP overhead at 1 thread, 5 runs each.", "tbl-noomp")


def load_phases():
    rows = list(csv.DictReader((RES / "phases.csv").open()))
    # Average the ranks within a run first, then take the median of the runs.
    by_run = defaultdict(list)
    for r in rows:
        by_run[(r["experiment"], r["variant"], int(r["ranks"]), int(r["threads"]), r["rep"])].append(r)
    out = defaultdict(list)
    for (exp, var, n, t, rep), ranks in by_run.items():
        out[(exp, var, n, t)].append({k: statistics.fmean([float(r[k]) for r in ranks]) for k in ("init", "compute", "exchange")})
    return out


def phases(ph):
    cols = lambda n, t, key: median([r[key] for r in ph[("phases", "x_overlap", n, t)]])
    md_rows, csv_rows = [], []
    for i, n in enumerate(RANKS):
        row = [n]
        out = [i, n]
        for t in (1, 4):
            c, e = cols(n, t, "compute"), cols(n, t, "exchange")
            row += [f"{c:.2f}", f"{e:.2f}"]
            out += [f"{c:.3f}", f"{e:.3f}"]
        md_rows.append(row)
        csv_rows.append(out)
    write_csv("phases.csv", ["idx", "ranks", "c1", "e1", "c4", "e4"], csv_rows)
    write_table("phases.md", ["Ranks", "1t comp", "1t exch", "4t comp", "4t exch"], md_rows,
                "Compute and exchange wait (s) per rank, 3 runs each.",
                "tbl-phases")


def exchange(rows, ph):
    g = group(rows, "exchange")
    md_rows, csv_rows, total_rows = [], [], []
    for var, label in EXCHANGE:
        row = [label]
        out = [var]
        total = [label]
        for n in (2, 4, 6):
            for t in (1, 4):
                row.append(f"{median([r['exchange'] for r in ph[('exchange', var, n, t)]]):.3f}")
                out.append(f"{median(g[(var, n, t)]):.3f}")
                total.append(f"{median(g[(var, n, t)]):.3f}")
        md_rows.append(row)
        csv_rows.append(out)
        total_rows.append(total)
    write_csv("exchange_elapsed.csv", ["variant", "n2t1", "n2t4", "n4t1", "n4t4", "n6t1", "n6t4"], csv_rows)
    head = ["Exchange", "2r 1t", "2r 4t", "4r 1t", "4r 4t", "6r 1t", "6r 4t"]
    write_table("exchange_total.md", head, total_rows, "Total time (s) by exchange, 10 runs each.",
                "tbl-exchange-total", ["l"] + ["r"] * 6)
    write_table("exchange.md", head, md_rows, "Time blocked in the exchange (s) per rank, 10 runs each.",
                "tbl-exchange", ["l"] + ["r"] * 6)


def verify():
    rows = list(csv.DictReader((RES / "verify.csv").open()))
    groups = defaultdict(list)
    for r in rows:
        variant = "variants" if r["program"].startswith("x_") else r["program"]
        groups[(variant, f"{r['size']} {r['max_time']} {r['interval']}", r["reference"])].append(r)
    md_rows = []
    for (program, args, reference_name), mine in groups.items():
        ranks = sorted({int(r["ranks"]) for r in mine})
        threads = sorted({int(r["threads"]) for r in mine})
        md_rows.append([program, args, f"{ranks[0]}-{ranks[-1]}" if len(ranks) > 1 else ranks[0],
                        ",".join(map(str, threads)), reference_name,
                        f"{sum(r['match'] == 'yes' for r in mine)} of {len(mine)}"])
    write_table("verify.md", ["Program", "Args", "Ranks", "Threads", "Against", "Match"], md_rows,
                "Output comparisons.", "tbl-verify", ["l", "l", "r", "r", "l", "r"])
    return len(rows), sum(r["match"] == "yes" for r in rows)


def main():
    rows = load_runs()
    seq_runs = group(rows, "sequential")
    seq, pseq = median(seq_runs[("seq", 1, 1)]), median(seq_runs[("prof_seq", 1, 1)])
    g, base, spreads = matrix(rows)
    req = requirements(g, base, seq)
    change(rows, base)
    reference(rows, seq, pseq)
    noomp(rows)
    ph = load_phases()
    phases(ph)
    exchange(rows, ph)
    checks, matches = verify()
    used = [r for r in rows if r["experiment"] != "smoke"]
    best = min(((median(v), k) for k, v in g.items() if k[2] in THREADS))
    inits = [r["init"] for k, v in ph.items() if k[0] == "phases" for r in v]
    stats = {
        "init_max": f"{max(inits):.4f}",
        "runs": len(used), "failed": sum(not r["ok"] for r in used),
        "checks": checks, "matches": matches, "seq": f"{seq:.3f}", "prof_seq": f"{pseq:.3f}",
        "base": f"{base:.3f}", "best_time": f"{best[0]:.3f}", "best_config": f"{best[1][1]}r{best[1][2]}t",
        "spread_median_pct": f"{statistics.median(spreads):.1f}", "spread_max_pct": f"{max(spreads):.1f}",
        "load_min": f"{min(r['load'] for r in used):.2f}", "load_max": f"{max(r['load'] for r in used):.2f}",
        "best_threads": req["best_threads"], "in_range_threads": req["in_range_threads"],
    }
    (SUMMARY / "stats.csv").write_text("key,value\n" + "".join(f"{k},{v}\n" for k, v in stats.items()))
    print("summary written:", ", ".join(sorted(p.name for p in TABLES.glob("*.md"))))
    print(stats)


if __name__ == "__main__":
    main()
