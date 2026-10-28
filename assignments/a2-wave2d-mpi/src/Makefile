# Program 2: Wave2D (sequential) and Wave2D_mpi (MPI + OpenMP).
# The course compiles with plain `g++` / `mpic++ -fopenmp` and no -O flag,
# so no optimization level is set here.
CXX      ?= g++
MPICXX   ?= mpicxx
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra
OUT       = ../out

# Wave2D_mpi joins the default build once Wave2D_mpi.cpp exists.
PROGS = Wave2D $(if $(wildcard Wave2D_mpi.cpp),Wave2D_mpi)

# make run P=Wave2D ARGS="100 500 10"
# make run P=Wave2D_mpi NP=4 ARGS="100 500 10 4"
# Add "| java -cp ../out Wout 100" by hand to watch the wave.
P    ?= Wave2D
NP   ?= 4
ARGS ?= 100 500 10

# MPICH2 1.2.1p1 (hydra) in the dev container, as on cssmpi. Nothing is
# needed for a single-machine run; the cluster script adds its hostfile.
MPIRUN       ?= mpirun
MPIRUN_FLAGS ?=

ifneq ($(filter run,$(MAKECMDGOALS)),)
ifeq ($(filter $(P),Wave2D Wave2D_mpi),)
$(error P=$(P) is not one of: Wave2D Wave2D_mpi)
endif
endif

# Wout.class is skipped where there is no javac (the cluster nodes).
all: $(addprefix $(OUT)/,$(PROGS)) $(if $(shell command -v javac),$(OUT)/Wout.class)

$(OUT)/Wave2D: Wave2D.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ Wave2D.cpp Timer.cpp

# MPICH2 1.2.1's mpicxx.h trips -Wextra on its own code. Treating the MPI
# include directory as a system directory keeps those warnings out while
# leaving warnings for Wave2D_mpi.cpp itself on.
MPI_ISYSTEM = $(patsubst -I%,-isystem %,$(filter -I%,$(shell $(MPICXX) -show)))

$(OUT)/Wave2D_mpi: Wave2D_mpi.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(MPICXX) $(CXXFLAGS) $(MPI_ISYSTEM) -fopenmp -o $@ Wave2D_mpi.cpp Timer.cpp

$(OUT)/Wout.class: Wout.java
	mkdir -p $(OUT)
	javac -d $(OUT) Wout.java

run: $(OUT)/$(P)
ifeq ($(P),Wave2D_mpi)
	$(MPIRUN) $(MPIRUN_FLAGS) -np $(NP) $(OUT)/$(P) $(ARGS)
else
	$(OUT)/$(P) $(ARGS)
endif

# Correctness checks against the professor's out1.txt (100 x 100, 500 steps,
# printed every 10). Both must print nothing from cmp.
check: $(OUT)/Wave2D
	$(OUT)/Wave2D 100 500 10 > $(OUT)/check1.txt
	cmp $(OUT)/check1.txt out1.txt && echo "Wave2D matches out1.txt"

THREADS ?= 4
check-mpi: $(OUT)/Wave2D_mpi
	$(MPIRUN) $(MPIRUN_FLAGS) -np $(NP) $(OUT)/Wave2D_mpi 100 500 10 $(THREADS) > $(OUT)/check$(NP).txt
	cmp $(OUT)/check$(NP).txt out1.txt && echo "Wave2D_mpi with $(NP) ranks matches out1.txt"

clean:
	rm -rf $(OUT)

.PHONY: all run check check-mpi clean
