# Program 2 Benchmarks

These scripts measure `Wave2D_mpi` on six CSSMPI machines and turn the results into the tables, charts and diagram in `../writeup.qmd`. Every run happens on CSSMPI inside `~/prog2`, built with the course's own `compile.sh`, so the timings match how the program is graded (`g++` and `mpic++ -fopenmp`, no optimization flag).

## Files

| File | Runs on | Purpose |
| :--- | :--- | :--- |
| `run_cssmpi.py` | local | Driver: `all`, `push`, `start`, `status`, `pull`, `clean`, plus `run`, `put` and `get` for one-off commands. Reads `.local/cssmpi.env`, masks connection details in all output, and refuses remote paths outside `~/prog2`. |
| `make_variants.py` | local | Writes one source folder per experiment into `build/variants/` (gitignored). |
| `bench.py` | CSSMPI | Builds everything, boots the mpd ring, runs the experiments one at a time, and closes the ring. Needs Python 3.9 or newer, which CSSMPI has. |
| `summarize.py` | local | Reads `results/` and writes `results/summary/*.csv` (chart data) and `results/tables/*.md` (report tables). |
| `make_figures.py` | local | Draws `../figures/ghost-exchange.drawio.svg`, which also opens in draw.io for editing. |
| `results/` | local | Raw data pulled back from CSSMPI: `runs.csv`, `phases.csv`, `verify.csv`, `verify_session.txt`, `machine.txt`, `progress.log`, `logs/`. |

All five scripts are Python with no third-party packages.

## Setup

Create `.local/cssmpi.env` in the repo root. The `.local/` folder is gitignored, so these values never reach the repo.

```sh
USER_NAME=...        # CSSMPI login
USER_PWD=...         # CSSMPI password
USER_HOME_DIR=...    # your home directory on CSSMPI
CLASS_HOME_DIR=...   # the course directory that holds the professor's prog2
SSH_PORT=...
SSH_ADDRESS=...      # the master node, for example one of cssmpi1h to cssmpi12h
```

On CSSMPI, follow `../src/mpi_setup.txt` once: `~/.mpd.conf`, passwordless SSH between the nodes, MPICH2 1.2.1p1 on `PATH` in `~/.bash_profile`, and `~/mpd.hosts` listing five other nodes. `~/prog2` must already hold the course files (`compile.sh`, `Timer.*`, `Wout.java`). Locally the scripts need `ssh`, `scp`, `bash` (to read the env file) and `python3`. The hosts are on private addresses, so the UW VPN has to be on.

## Running

One command runs everything from the repo root:

```sh
assignments/a2-wave2d-mpi/bench/run_cssmpi.py all     # about 40 minutes
scripts/build-writeup.sh a2-wave2d-mpi                # render the report to PDF
```

`all` pushes and builds, starts the suite, waits for it, pulls the results, summarizes them, draws the figure and cleans up `~/prog2/bench`. If the suite does not finish, it stops before cleaning and leaves the remote files in place.

The same steps can be run by hand:

```sh
assignments/a2-wave2d-mpi/bench/run_cssmpi.py push    # copy the sources, variants and bench.py; build them
assignments/a2-wave2d-mpi/bench/run_cssmpi.py start   # run every experiment in the background
assignments/a2-wave2d-mpi/bench/run_cssmpi.py status  # latest progress lines and RUNNING or IDLE
assignments/a2-wave2d-mpi/bench/run_cssmpi.py pull    # copy the remote results into bench/results/
python3 assignments/a2-wave2d-mpi/bench/summarize.py  # rebuild the report tables and chart data
python3 assignments/a2-wave2d-mpi/bench/make_figures.py
assignments/a2-wave2d-mpi/bench/run_cssmpi.py clean   # remove ~/prog2/bench on CSSMPI
```

`push` overwrites `Wave2D.cpp`, `Wave2D_mpi.cpp` and the `compile.sh` outputs in `~/prog2` with the versions in `../src`. The `verify` phase writes `out1.txt` and `out6.txt` there under the handout's names. `clean` removes only `~/prog2/bench`, closes any ring left open, and refuses to run while a benchmark is still going.

To run part of the suite, name the phases, for example `assignments/a2-wave2d-mpi/bench/run_cssmpi.py start matrix exchange`. A run whose log already contains `Elapsed time` is skipped, so an interrupted phase can be started again and only the missing runs execute. A lock keeps two benchmark processes from running at the same time.

## The mpd Ring

`bench.py` boots the ring with `CSSmpdboot -n 6 -v` from the home directory and closes it with `mpdallexit` when it exits, even after an error. Three details of CSSMPI shape this:

- `CSSmpdboot` leaves `mpd` attached to its output, so piping it into `tail` or `grep` hangs forever. It writes to `bench/mpdboot.log` instead, which stays out of `results/` because it holds cluster addresses.
- `CSSmpdboot` ignores `-n` and starts every host in `~/mpd.hosts` plus the master.
- A plain SSH command gets MPICH 5 from `/etc/profile.d`. `run_cssmpi.py` wraps every remote command in `bash -lc`, which puts the course's MPICH2 1.2.1p1 first.

## Experiments

| Phase | What it measures | Runs |
| :--- | :--- | :--- |
| `verify` | The handout's `diff` session, then byte comparisons across ranks 1 to 6, a size that does not divide evenly (233), and every variant. | 1 each |
| `sequential` | `./Wave2D 588 500 0`, alternating with the professor's. | 10 each |
| `matrix` | `Wave2D_mpi 588 500 0` at ranks 1 to 6 and threads 1 to 6, 8 and 10. The handout requires threads 1 to 4; 5 and 10 are the cores and logical CPUs of one node. | 10 per pair |
| `noomp` | The program with the `omp` pragma removed against the normal build at 1 thread, at ranks 1 to 6, so the cost of the OpenMP region shows up on its own. | 5 per pair |
| `reference` | This program and the professor's `Wave2D_mpi`, alternating within each round so both meet the same load. | 10 per pair |
| `phases` | Compute, exchange and init time per rank. | 3 per pair |
| `exchange` | The overlap in `../src` against the same async calls with no overlap, and against blocking exchanges: left first, right first, and left first before the compute. | 10 per variant |

Each variant differs from `../src/Wave2D_mpi.cpp` by exactly one change plus the timers, so any difference comes from that change. `bench.py` cycles through all configurations in each round to spread changes in machine load across them. It records the highest 1-minute load across the six nodes next to every run. The report's speedups use medians, so one run hit by someone else's job does not move a result. The mean sits next to the median in the main tables, and every run stays in `results/runs.csv`.

## Notes

- CSSMPI is shared. Check the `load_max` column in `results/runs.csv` before trusting a single run. A node with 5 cores running 10 threads shows a load near 10 from the program itself.
- Ranks land one per node, so up to 6 ranks never share a machine.
- `results/` must not hold the home directory or login. `bench.py` replaces the class directory in logs and keeps the ring's boot log out of `results/`.
- The professor's binaries are only run from the class directory, never copied or modified.
