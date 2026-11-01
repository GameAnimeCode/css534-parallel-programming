# Program 2: Parallelizing Wave Diffusion with MPI and OpenMP

A two-dimensional wave simulation (`Wave2D.cpp`), parallelized with MPI across machines and OpenMP within each machine (`Wave2D_mpi.cpp`). The assignment text is in `CSS-534_Program-02.pdf`.

## Files

| Path | What it is |
|---|---|
| `src/Wave2D_template.cpp` | Handout. The sequential program with the simulation loop left to write. |
| `src/Wave2D.cpp` | My sequential version, started from the template. |
| `src/Wave2D_mpi.cpp` | My MPI and OpenMP version, started from `Wave2D.cpp` once it works. |
| `src/Timer.h`, `src/Timer.cpp` | Handout. Wall-clock timer, prints "Elapsed time" in microseconds. |
| `src/Wout.java` | Handout. Reads the program's output from a pipe and animates it. |
| `src/out1.txt` | Handout. Output of the professor's `Wave2D 100 500 10`, used by `make check`. |
| `src/measurements*.txt`, `src/measurements.xlsx` | Handout. The professor's timings from earlier years. |
| `src/mpd.hosts`, `src/mpi_setup.txt`, `src/setup_mpi_cluster.sh` | Handout. CSSMPI cluster setup notes. |
| `src/Wave2D`, `src/Wave2D_mpi` | Handout. The professor's executables, kept locally as oracles but not tracked in git. |
| `lab/` | Lab 2: `greetings.cpp`, `matrix.cpp`, and `matrix_mpi.cpp`. |
| `cluster/` | Four containers that act as a local MPI cluster. |
| `bench/` | Benchmarks run on CSSMPI and their results. See `bench/README.md`. |
| `figures/` | The report's diagram, editable in draw.io. |
| `writeup.qmd` | The report. Build it with `scripts/build-writeup.sh a2-wave2d-mpi`. |

## Build and Run

The dev container has MPICH2 1.2.1p1 at `/usr/apps/mpich121-x86_64`, the same install CSSMPI uses, so `mpic++` and `mpirun` behave the same here and there.

```bash
cd src
make                                        # Wave2D, Wout.class, and Wave2D_mpi once it exists
make run P=Wave2D ARGS="100 500 10"
make run P=Wave2D_mpi NP=4 ARGS="100 500 10 4"   # 4 ranks, 4 threads each
```

Arguments are `size max_time interval`, plus the thread count for the MPI version. An interval of 0 prints nothing, which is how timing runs are done.

`make run` with the MPI program launches all ranks on this machine. Nothing else is needed for that; the dev container sets `HYDRA_BOOTSTRAP=fork`.

## Checking Correctness

`src/out1.txt` is the professor's output for a 100 x 100 space, 500 steps, printed every 10. Both targets below compare against it and print a confirmation line when the output is identical:

```bash
make check                    # Wave2D 100 500 10
make check-mpi NP=4 THREADS=2 # Wave2D_mpi 100 500 10 2 on 4 ranks
```

Two details of that file matter for matching it. The professor's program prints at the top of iteration `t` the buffer it is about to overwrite, so the frame under header `t` holds the state at time `t - 3` (all zeros at `t = 2`). Frames appear at every multiple of the interval and at the final step `max_time - 1`. Each row ends with a space and each frame with a blank line.

The professor's `Wave2D` and `Wave2D_mpi` executables also run here against the same libraries, so they can be used to compare timings or produce reference output for other sizes:

```bash
./Wave2D 200 300 5 > ref.txt
mpirun -np 2 ./Wave2D_mpi 200 300 5 2 | cmp - ref.txt
```

## Watching the Wave

`Wout.java` draws each frame in a window. Pipe a run into it with the same size:

```bash
./Wave2D 100 500 10 | java -cp ../out Wout 100
make run P=Wave2D_mpi NP=4 ARGS="100 500 10 4" | java -cp ../out Wout 100
```

VS Code forwards the host's X socket into the dev container, but not the X authorization cookie, so Java cannot open the window until the host allows it. Once per login, in a terminal on the host itself (not a VS Code terminal, which runs inside the container):

```bash
xhost +si:localuser:$USER
```

This admits local X connections from your own user, which is what the container runs as. It is narrower than a bare `xhost +`, which turns access control off for everyone. Any X11 client can see other X11 windows' input, so this is a grant of trust to code running in the container.

## Local MPI Cluster

`mpirun -np 4` on one machine does not exercise the network. `cluster/` starts four containers (`node1` to `node4`) on a private network, each with MPICH2 1.2.1p1, SSH between them, a four-CPU quota, and this repository mounted at `/workspace`, the same path as in the dev container. Binaries built here run on the nodes unchanged.

```bash
cluster/cluster.sh up                      # build the image once, then start the nodes
cd src && make
../cluster/cluster.sh mpirun -np 4 ../out/Wave2D_mpi 100 500 10 4
../cluster/cluster.sh mpirun -np 4 ../out/Wave2D_mpi 100 500 10 4 | java -cp ../out Wout 100
../cluster/cluster.sh ssh node2            # shell on a node
../cluster/cluster.sh down                 # stop the nodes
```

`cluster.sh mpirun` runs hydra's `mpiexec -f /etc/mpi/hostfile` on `node1` in the node's copy of the current directory, so relative paths work as they do locally. Ranks go round-robin over the nodes, one per node per pass, the order the mpd ring on CSSMPI uses. With more ranks than nodes they double up.

The first `up` compiles MPICH2 from source inside the image, which takes a few minutes. Later starts reuse the image. The nodes have no Java and no display; run `Wout` in the dev container and pipe into it as above.

Limits: the four-CPU share is a quota, not pinned cores, and the laptop's compiler and CPUs differ from CSSMPI. Use the cluster for correctness and for the shape of the scaling, and take the report's timings on CSSMPI.

## Running on CSSMPI

Log in to one of `cssmpi1` through `cssmpi24`. Login shells there put MPICH2 1.2.1p1 first on `PATH` through `~/.bash_profile` (see `src/mpi_setup.txt`). The professor's `compile.sh` shows the exact build commands:

```bash
g++ Wave2D.cpp Timer.cpp -o Wave2D
mpic++ Wave2D_mpi.cpp Timer.cpp -fopenmp -o Wave2D_mpi
```

No optimization flag is used, so none is used here either.

CSSMPI launches through an mpd ring rather than hydra. `~/mpd.hosts` lists the other machines, `CSSmpdboot -n <machines> -v` starts the ring, `mpirun -np <ranks> ./Wave2D_mpi 588 500 0 <threads>` runs the program, and `mpdallexit` tears the ring down. Always run `mpdallexit` before logging out.

## Lab 2

`lab/` holds the lab 2 handout with its own Makefile:

```bash
cd lab
make
make run P=matrix ARGS=400
make run P=matrix_mpi NP=4 ARGS=400
../cluster/cluster.sh mpirun -np 4 ../out/lab/greetings
```
