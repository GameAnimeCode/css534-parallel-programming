#!/usr/bin/env python3
"""Summarize the CSSMPI benchmark results for the writeup.

Reads results/runs.csv, results/phases.csv and results/logs/, then writes
  results/summary/*.csv   small tables that the pgfplots charts read
  results/tables/*.md     Markdown tables that writeup.qmd includes
Run it after pulling new results: python3 bench/summarize.py
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SUMMARY = RES / "summary"
TABLES = RES / "tables"

PROF_1T_US = 23_543_059   # professor's 1-thread time from the spec
PROF_4T_US = 11_666_615   # professor's 4-thread time from the spec
TARGET_SPEEDUP = 2.02
TARGET_DISTANCE = 449.658
GEN0 = "generation: 0 shortest distance = 1265.72"
GEN0_ITIN = "V1SPMBQAN26G4J37DX8OTF95ZUH0EYRLCWKI"

CHUNK_LABELS = [
    ("xo_static", "static"), ("xo_guided", "guided"), ("xo_dyn1", "dynamic, 1"),
    ("xo_dyn8", "dynamic, 8"), ("xo_dyn16", "dynamic, 16"), ("src", "dynamic, 64"),
    ("xo_dyn256", "dynamic, 256"), ("xo_dyn1024", "dynamic, 1024"),
]


def load_runs():
    rows = list(csv.DictReader((RES / "runs.csv").open()))
    for r in rows:
        r["threads"] = int(r["threads"])
        r["load1"] = float(r["load1"])
        r["ok"] = bool(r["elapsed_us"])  # empty when the program failed to start
        r["sec"] = int(r["elapsed_us"]) / 1e6 if r["ok"] else float("nan")
        r["dist"] = float(r["best_distance"]) if r["ok"] else float("nan")
    return rows


def group(rows, experiment):
    """Map (variant, threads) to the list of elapsed seconds for one experiment."""
    out = defaultdict(list)
    for r in rows:
        if r["experiment"] == experiment:
            out[(r["variant"], r["threads"])].append(r["sec"])
    return out


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


def scaling(rows):
    g = group(rows, "scaling")
    threads = sorted({t for (_, t) in g})
    base = mean(g[("src", 1)])
    csv_rows, md_rows = [], []
    for t in threads:
        s = g[("src", t)]
        m = mean(s)
        dists = [r["dist"] for r in rows if r["experiment"] == "scaling" and r["threads"] == t]
        csv_rows.append([t, f"{m:.3f}", f"{min(s):.3f}", f"{max(s):.3f}", f"{base / m:.3f}",
                         f"{base / m / t:.3f}", f"{PROF_1T_US / 1e6 / m:.3f}"])
        md_rows.append([t, f"{m:.2f}", f"{min(s):.2f}", f"{max(s):.2f}", f"{base / m:.2f}",
                        f"{100 * base / m / t:.0f}%", f"{PROF_1T_US / 1e6 / m:.2f}",
                        f"{min(dists):.3f}"])
    write_csv("scaling.csv", ["threads", "mean", "min", "max", "speedup", "efficiency", "speedup_prof"], csv_rows)
    write_table("scaling.md",
                ["Threads", "Mean (s)", "Min (s)", "Max (s)", "Speedup", "Efficiency", "vs. prof.", "Best"],
                md_rows,
                "Scaling on CSSMPI-12, 5 runs per thread count. Speedup and efficiency are against the "
                "program's own 1-thread mean, and vs. prof. against the professor's 1-thread time (23.54s).", "tbl-scaling")
    return base, g


def chunk(rows):
    g = group(rows, "chunk")
    threads = sorted({t for (_, t) in g})
    csv_rows, md_rows = [], []
    for i, (var, label) in enumerate(CHUNK_LABELS):
        ms = [mean(g[(var, t)]) for t in threads]
        # pgfplots cannot read quoted CSV fields, so the chart label has no comma.
        csv_rows.append([i, label.replace(", ", " ")] + [f"{m:.3f}" for m in ms])
        md_rows.append([label] + [f"{m:.2f}" for m in ms])
    write_csv("chunk.csv", ["idx", "label"] + [f"t{t}" for t in threads], csv_rows)
    write_table("chunk.md", ["Schedule"] + [f"{t} threads (s)" for t in threads], md_rows,
                "Mean time by crossover schedule, 3 runs each.",
                "tbl-chunk", ["l"] + ["r"] * len(threads))


def two_way(rows, experiment, a, b, name, header, caption, label):
    g = group(rows, experiment)
    threads = sorted({t for (_, t) in g})
    csv_rows, md_rows = [], []
    for t in threads:
        ma, mb = mean(g[(a, t)]), mean(g[(b, t)])
        gain = 100 * (ma - mb) / ma
        csv_rows.append([t, f"{ma:.3f}", f"{mb:.3f}", f"{gain:.2f}"])
        md_rows.append([t, f"{ma:.2f}", f"{mb:.2f}", f"{gain:+.1f}%"])
    write_csv(f"{name}.csv", ["threads", a, b, "gain_pct"], csv_rows)
    write_table(f"{name}.md", header, md_rows, caption, label)


def amdahl(rows):
    g = group(rows, "amdahl")
    threads = sorted({t for (_, t) in g})
    variants = ["ev_only", "xo_only", "src"]
    base = {v: mean(g[(v, 1)]) for v in variants}
    csv_rows, md_rows = [], []
    for t in threads:
        ms = [mean(g[(v, t)]) for v in variants]
        csv_rows.append([t] + [f"{m:.3f}" for m in ms] + [f"{base[v] / m:.3f}" for v, m in zip(variants, ms)])
        md_rows.append([t] + [f"{m:.2f} ({base[v] / m:.2f}x)" for v, m in zip(variants, ms)])
    write_csv("amdahl.csv", ["threads", "ev_only", "xo_only", "both",
                             "ev_only_speedup", "xo_only_speedup", "both_speedup"], csv_rows)
    write_table("amdahl.md", ["Threads", "Only evaluate", "Only crossover", "Both"],
                md_rows, "Mean time in seconds with only one loop parallel, 3 runs each. Speedup over the same build "
                "at 1 thread in parentheses.",
                "tbl-amdahl")


def phases(runs):
    path = RES / "phases.csv"
    # phases.csv has no experiment column; keep only rows from the phases experiment.
    wanted = {r["elapsed_us"] for r in runs if r["experiment"] == "phases"}
    rows = [r for r in csv.DictReader(path.open()) if r["elapsed_us"] in wanted]
    keys = ["eval_loop_s", "sort_s", "select_s", "crossover_s", "mutate_s", "populate_s"]
    by_t = defaultdict(list)
    for r in rows:
        by_t[int(r["threads"])].append(r)
    csv_rows, md_rows = [], []
    for i, t in enumerate(sorted(by_t)):
        ms = [mean([float(r[k]) for r in by_t[t]]) for k in keys]
        total = sum(ms)
        csv_rows.append([i, t] + [f"{m:.3f}" for m in ms])
        md_rows.append([t] + [f"{m:.2f} ({100 * m / total:.0f}%)" for m in ms])
    write_csv("phases.csv", ["idx", "threads", "eval_loop", "sort", "select", "crossover", "mutate", "populate"], csv_rows)
    write_table("phases.md",
                ["Threads", "evaluate loop", "sort", "select", "crossover", "mutate", "populate"], md_rows,
                "Seconds per step over 150 generations, 3 runs each, with each step's share of the total.", "tbl-phases")


def simple_compare(rows, experiment, variants, labels, name, caption, label):
    g = group(rows, experiment)
    threads = sorted({t for (_, t) in g})
    md_rows = []
    for t in threads:
        md_rows.append([t] + [f"{mean(g[(v, t)]):.2f}" for v in variants])
    write_table(name, ["Threads"] + labels, md_rows, caption, label)


def correctness(rows):
    logs = sorted((RES / "logs").glob("*.txt"))
    gen0_ok = sum(1 for p in logs if GEN0 in (t := p.read_text()) and GEN0_ITIN in t)
    # The shortest-trip totals cover builds at MUTATE_RATE 50 (src/Trip.h); the mutation sweep's
    # other rates are reported separately in mutation.md.
    ours = [r for r in rows if r["ok"] and r["variant"] != "reference" and r["experiment"] != "smoke"
            and not r["variant"].startswith("mutate")]
    dists = sorted(r["dist"] for r in ours)
    meets = sum(1 for d in dists if d <= TARGET_DISTANCE)
    best = min(ours, key=lambda r: r["dist"])
    counts = defaultdict(int)
    for d in dists:
        counts[f"{d:.3f}"] += 1
    md_rows = [[k, v, "yes" if float(k) <= TARGET_DISTANCE else "no"] for k, v in sorted(counts.items())]
    write_table("distances.md", ["Shortest trip", "Runs", "Meets 449.658"], md_rows,
                f"Shortest distance over {len(dists)} runs.", "tbl-distances",
                ["r", "r", "c"])
    loads = [r["load1"] for r in rows if r["experiment"] != "smoke"]
    stats = {
        "runs": len(dists), "meets": meets, "logs": len(logs), "gen0_ok": gen0_ok,
        "best": f"{best['dist']:.3f}", "best_itin": best["best_itinerary"],
        "median": f"{statistics.median(dists):.3f}", "worst": f"{max(dists):.3f}",
        "load_min": f"{min(loads):.2f}", "load_max": f"{max(loads):.2f}",
    }
    (SUMMARY / "stats.csv").write_text("key,value\n" + "".join(f"{k},{v}\n" for k, v in stats.items()))
    return stats


def reference(rows, base_1t):
    ref = [r for r in rows if r["experiment"] == "reference"]
    ours = group(rows, "scaling")
    md_rows = []
    for r in sorted(ref, key=lambda r: r["threads"]):
        mine = mean(ours[("src", r["threads"])])
        if r["ok"]:
            md_rows.append([r["threads"], f"{r['sec']:.2f}", f"{r['dist']:.3f}", f"{mine:.2f}"])
        else:
            md_rows.append([r["threads"], "did not start", "n/a", f"{mine:.2f}"])
    write_table("reference.md", ["Threads", "Prof. Tsp (s)", "Prof. best", "Mean (s)"],
                md_rows, "The professor's Tsp on the same machine, 1 run per thread count.", "tbl-reference")


def amdahl_prediction(scaling_runs, base):
    """Amdahl's law from the 1-thread phase split, against the measured scaling speedups."""
    ph = {int(r["threads"]): r for r in csv.DictReader((SUMMARY / "phases.csv").open())}
    one = ph[1]
    serial = sum(float(one[k]) for k in ("sort", "select", "mutate", "populate"))
    total = serial + float(one["eval_loop"]) + float(one["crossover"])
    s = serial / total
    measured = {t: base / mean(scaling_runs[("src", t)]) for (_, t) in scaling_runs}
    md_rows = []
    for n in (2, 3, 4, 5, 8, 10):
        predicted = 1 / (s + (1 - s) / n)
        md_rows.append([n, f"{predicted:.2f}", f"{measured[n]:.2f}", f"{100 * measured[n] / predicted:.0f}%"])
    write_table("amdahl_prediction.md", ["Threads", "Predicted", "Measured", "Ratio"], md_rows,
                f"Amdahl's law (s = {s:.4f}) against measured speedup, with ratio = measured / predicted. "
                "Above 5 threads the extra threads "
                "are hyperthreads, not cores.",
                "tbl-amdahl-prediction")


MUTATE_VARIANTS = [("mutate0", 0), ("mutate10", 10), ("mutate25", 25), ("src", 50),
                   ("mutate75", 75), ("mutate100", 100)]


def mutation(rows):
    runs = [r for r in rows if r["experiment"] == "mutation" and r["ok"]]
    if not runs:
        return
    md_rows, points = [], []
    for var, rate in MUTATE_VARIANTS:
        mine = [r for r in runs if r["variant"] == var]
        dists = sorted(r["dist"] for r in mine)
        secs = [r["sec"] for r in mine]
        md_rows.append([rate, f"{mean(secs):.2f}", f"{dists[0]:.3f}",
                        f"{statistics.median(dists):.3f}", f"{dists[-1]:.3f}",
                        f"{sum(d <= TARGET_DISTANCE for d in dists)} of {len(dists)}"])
        # Spread identical results sideways so every run stays visible in the dot chart.
        seen = defaultdict(int)
        for d in dists:
            k = seen[d]
            seen[d] += 1
            offset = (k - 4.5) * 0.6 if dists.count(d) > 1 else 0.0
            points.append([rate, f"{rate + offset:.2f}", f"{d:.3f}"])
    write_csv("mutation_runs.csv", ["rate", "x", "distance"], points)
    write_table("mutation.md", ["Rate (%)", "Mean (s)", "Best", "Median", "Worst",
                                "Meets 449.658"], md_rows,
                "Mutation rate at 5 threads, 10 runs each. Trip.h sets 50.",
                "tbl-mutation")


def main():
    rows = load_runs()
    base, scaling_runs = scaling(rows)
    chunk(rows)
    two_way(rows, "static_vs_dynamic", "xo_static", "src", "static_vs_dynamic",
            ["Threads", "Static (s)", "Dynamic, 64 (s)", "Change"],
            "Static against dynamic, 64 scheduling for crossover, 3 runs each.",
            "tbl-static-dynamic")
    two_way(rows, "ev_schedule", "src", "ev_dyn64", "ev_schedule",
            ["Threads", "Static (s)", "Dynamic, 64 (s)", "Change"],
            "Static against dynamic, 64 scheduling for evaluate, 3 runs each.", "tbl-ev-schedule")
    amdahl(rows)
    simple_compare(rows, "serial", ["serial", "src"], ["No OpenMP (s)", "OpenMP (s)"],
                   "serial.md", "OpenMP overhead at 1 thread, 5 runs each.", "tbl-serial")
    phases(rows)
    amdahl_prediction(scaling_runs, base)
    mutation(rows)
    stats = correctness(rows)
    reference(rows, base)
    print("summary written:", ", ".join(sorted(p.name for p in TABLES.glob("*.md"))))
    print(stats)


if __name__ == "__main__":
    main()
