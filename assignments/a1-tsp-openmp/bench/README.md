# Program 1 Benchmarks

These scripts measure the OpenMP TSP program on a CSSMPI machine and turn the results into the tables and charts in `../writeup.qmd`. Every run happens on CSSMPI inside `~/prog1`, built with the course's own `compile.sh`, so the timings match how the program is graded (`g++ -fopenmp`, no optimization flag).

## Files

| File | Runs on | Purpose |
| :--- | :--- | :--- |
| `run_cssmpi.py` | local | Driver: `push`, `start`, `status`, `pull`, `clean`, plus `run`, `put` and `get` for one-off commands. Reads `.local/cssmpi.env`, masks connection details in all output, and refuses remote paths outside `~/prog1`. |
| `make_variants.py` | local | Writes one source folder per experiment into `build/variants/` (gitignored). |
| `bench.py` | CSSMPI | Builds everything and runs the experiments, one run at a time. Needs Python 3.9 or newer, which CSSMPI has. |
| `summarize.py` | local | Reads `results/` and writes `results/summary/*.csv` (chart data) and `results/tables/*.md` (report tables). |
| `results/` | local | Raw data pulled back from CSSMPI: `runs.csv`, `phases.csv`, `machine.txt`, `progress.log`, `logs/`. |

All four scripts are Python with no third-party packages.

## Setup

Create `.local/cssmpi.env` in the repo root. The `.local/` folder is gitignored, so these values never reach the repo.

```sh
USER_NAME=...        # CSSMPI login
USER_PWD=...         # CSSMPI password
USER_HOME_DIR=...    # your home directory on CSSMPI
CLASS_HOME_DIR=...   # the course directory that holds the professor's prog1
SSH_PORT=...
SSH_ADDRESS=...      # for example one of cssmpi1h to cssmpi12h
```

`~/prog1` on CSSMPI must already hold the course files (`compile.sh`, `Trip.h`, `Timer.*`, `chromosome.txt`, `cities.txt`). Locally the scripts need `ssh`, `scp`, `bash` (to read the env file) and `python3`. No `sshpass` is needed. `run_cssmpi.py` passes the password to OpenSSH through `SSH_ASKPASS` and keeps one shared connection open for 30 minutes, so the password is sent once.

## Running

From the repo root:

```sh
assignments/a1-tsp-openmp/bench/run_cssmpi.py push    # copy src/*.cpp, the variants and bench.py; build them
assignments/a1-tsp-openmp/bench/run_cssmpi.py start   # run every experiment in the background (about 45 minutes)
assignments/a1-tsp-openmp/bench/run_cssmpi.py status  # latest progress lines and RUNNING or IDLE
assignments/a1-tsp-openmp/bench/run_cssmpi.py pull    # copy the remote results into bench/results/
python3 assignments/a1-tsp-openmp/bench/summarize.py  # rebuild the report tables and chart data
scripts/build-writeup.sh a1-tsp-openmp                # render the report to PDF
assignments/a1-tsp-openmp/bench/run_cssmpi.py clean   # remove ~/prog1/bench on CSSMPI when you are done
```

`push` overwrites `EvalXOverMutate.cpp`, `Tsp.cpp` and the `compile.sh` outputs in `~/prog1` with the versions in `../src`. `clean` removes only `~/prog1/bench`, so your final sources and the program built from them stay in place. It refuses to run while a benchmark is still going.

To run part of the suite, name the phases, for example `assignments/a1-tsp-openmp/bench/run_cssmpi.py start scaling schedule`. A run whose log already ends with `elapsed time` is skipped, so an interrupted phase can be started again and only the missing runs execute. A lock keeps two benchmark processes from running at the same time.

## Experiments

| Phase | What it measures | Runs |
| :--- | :--- | :--- |
| `scaling` | The program built from `../src` at 1 to 10 threads (5 cores with 2 hyperthreads each on the test host) and at 12, 16 and 20 threads, which oversubscribe it. | 5 per thread count |
| `schedule` | crossover with `static`, `guided` and `dynamic` at chunk sizes 1 to 1024; then static against `dynamic, 64` across thread counts. | 3 each |
| `evaluate` | evaluate with `static` against `dynamic, 64`. | 3 each |
| `amdahl` | Only evaluate parallel, only crossover parallel, both, and a build with no OpenMP pragmas. | 3 to 5 each |
| `reference` | One run of the professor's binary as an output check. | 1 per thread count |
| `phases` | Time spent in the evaluate loop, the sort, select, crossover, mutate and populate. | 3 per thread count |
| `mutation` | `MUTATE_RATE` at 0, 10, 25, 50, 75 and 100 at 5 threads, for trip quality. Each rate's variant carries its own `Trip.h`. | 10 per rate |

Each variant differs from `../src` by exactly one change, so any difference in timing comes from that change. `bench.py` cycles through all configurations in each round to spread changes in machine load across them. It also records the 1-minute load average next to every run.

## Notes

- CSSMPI is shared. Check the `load1` column in `results/runs.csv` before trusting a single run.
- Results vary between runs because `main` seeds `rand()` with the time.
- The professor's binary is only run, never copied or modified. On the test host it would not start (`GLIBCXX_3.4.32 not found`, because it was built with a newer GCC than the host's g++ 11.5), so the `reference` rows in `runs.csv` are empty.
