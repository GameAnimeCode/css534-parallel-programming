#!/usr/bin/env python3
"""Generate one source folder per benchmark variant from ../src.

Each variant changes exactly one thing in the code in src/ (a schedule
clause, a removed pragma, or timing instrumentation), so any difference in
the measurements comes from that one change. Output goes to build/variants/,
which is gitignored. A variant folder always holds EvalXOverMutate.cpp, and
holds Tsp.cpp or Trip.h only when they differ from the ones in src/. Because
EvalXOverMutate.cpp includes "Trip.h" with quotes, a Trip.h next to it wins.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
OUT = HERE / "build" / "variants"

EVAL = (SRC / "EvalXOverMutate.cpp").read_text()
TSP = (SRC / "Tsp.cpp").read_text()
TRIP = (SRC / "Trip.h").read_text()
MUTATE_LINE = "#define MUTATE_RATE    50"
MUTATE_RATES = (0, 10, 25, 75, 100)  # 50 is the value in src/Trip.h

EV_PRAGMA = "#pragma omp parallel for\n"
XO_REGION = "#pragma omp parallel\n"
XO_FOR = "#pragma omp for schedule(dynamic, 64)\n"


def swap(text, old, new):
    """Replace a snippet that must appear exactly once."""
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected 1 match, found {count}: {old!r}")
    return text.replace(old, new)


def xo_schedule(clause):
    return swap(EVAL, XO_FOR, f"#pragma omp for{clause}\n")


def profiled():
    """Time the evaluate loop and sort separately, plus every Tsp phase."""
    ev = swap(EVAL, "using namespace std;\n",
              "using namespace std;\n\ndouble prof_eval_loop = 0.0, prof_sort = 0.0;\n")
    ev = swap(ev, EV_PRAGMA, "  double prof_t0 = omp_get_wtime();\n" + EV_PRAGMA)
    ev = swap(ev, "  sort(trip, trip + CHROMOSOMES,",
              "  double prof_t1 = omp_get_wtime();\n  sort(trip, trip + CHROMOSOMES,")
    ev = swap(ev, "       { return lhs.fitness < rhs.fitness; });\n}",
              "       { return lhs.fitness < rhs.fitness; });\n"
              "  prof_eval_loop += prof_t1 - prof_t0;\n"
              "  prof_sort += omp_get_wtime() - prof_t1;\n}")

    tsp = swap(TSP, "using namespace std;\n",
               "using namespace std;\n\nextern double prof_eval_loop, prof_sort;\n"
               "static double prof_select = 0, prof_xover = 0, prof_mutate = 0, prof_populate = 0;\n")

    def timed(src, call, acc):
        return swap(src, f"    {call}\n",
                    f"    {{ double t = omp_get_wtime(); {call} {acc} += omp_get_wtime() - t; }}\n")

    tsp = timed(tsp, "select(trip, parents);", "prof_select")
    tsp = timed(tsp, "crossover(parents, offsprings, coordinates);", "prof_xover")
    tsp = timed(tsp, "mutate(offsprings);", "prof_mutate")
    tsp = timed(tsp, "populate(trip, offsprings);", "prof_populate")
    tsp = swap(tsp, '  cout << "elapsed time = " << timer.lap() << endl;\n',
               '  cout << "elapsed time = " << timer.lap() << endl;\n'
               '  cout << "PHASES threads=" << nThreads\n'
               '       << " eval_loop=" << prof_eval_loop << " sort=" << prof_sort\n'
               '       << " select=" << prof_select << " crossover=" << prof_xover\n'
               '       << " mutate=" << prof_mutate << " populate=" << prof_populate << endl;\n')
    return ev, tsp


def main():
    variants = {
        "xo_static": xo_schedule(""),
        "xo_guided": xo_schedule(" schedule(guided)"),
        "ev_dyn64": swap(EVAL, EV_PRAGMA, "#pragma omp parallel for schedule(dynamic, 64)\n"),
        "ev_only": swap(swap(EVAL, XO_REGION, ""), XO_FOR, ""),
        "xo_only": swap(EVAL, EV_PRAGMA, ""),
        "serial": swap(swap(swap(EVAL, EV_PRAGMA, ""), XO_REGION, ""), XO_FOR, ""),
    }
    for chunk in (1, 8, 16, 256, 1024):
        variants[f"xo_dyn{chunk}"] = xo_schedule(f" schedule(dynamic, {chunk})")

    OUT.mkdir(parents=True, exist_ok=True)
    for name, source in variants.items():
        folder = OUT / name
        folder.mkdir(exist_ok=True)
        (folder / "EvalXOverMutate.cpp").write_text(source)

    for rate in MUTATE_RATES:
        folder = OUT / f"mutate{rate}"
        folder.mkdir(exist_ok=True)
        (folder / "EvalXOverMutate.cpp").write_text(EVAL)
        (folder / "Trip.h").write_text(swap(TRIP, MUTATE_LINE, f"#define MUTATE_RATE    {rate:<3}"))

    ev, tsp = profiled()
    folder = OUT / "phases"
    folder.mkdir(exist_ok=True)
    (folder / "EvalXOverMutate.cpp").write_text(ev)
    (folder / "Tsp.cpp").write_text(tsp)

    print(f"wrote {len(variants) + len(MUTATE_RATES) + 1} variants to {OUT.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
