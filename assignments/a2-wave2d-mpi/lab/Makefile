CXX      ?= g++
MPICXX   ?= mpicxx
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra
OUT       = ../out/lab

PROGS     = greetings matrix matrix_mpi
MPI_PROGS = greetings matrix_mpi

# make run P=matrix ARGS=400
# make run P=matrix_mpi NP=4 ARGS=400
P    ?= matrix_mpi
NP   ?= 4
ARGS ?= 400

MPIRUN       ?= mpirun
MPIRUN_FLAGS ?=

ifneq ($(filter run,$(MAKECMDGOALS)),)
ifeq ($(filter $(P),$(PROGS)),)
$(error P=$(P) is not one of: $(PROGS))
endif
endif

# MPICH2 1.2.1's mpicxx.h trips -Wextra on its own code. Treating the MPI
# include directory as a system directory keeps those warnings out while
# leaving warnings for the lab sources on.
MPI_ISYSTEM = $(patsubst -I%,-isystem %,$(filter -I%,$(shell $(MPICXX) -show)))

all: $(addprefix $(OUT)/,$(PROGS))

$(OUT)/greetings: greetings.cpp
	mkdir -p $(OUT)
	$(MPICXX) $(CXXFLAGS) $(MPI_ISYSTEM) -o $@ $<

$(OUT)/matrix: matrix.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ $< Timer.cpp

$(OUT)/matrix_mpi: matrix_mpi.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(MPICXX) $(CXXFLAGS) $(MPI_ISYSTEM) -o $@ $< Timer.cpp

run: $(OUT)/$(P)
ifneq ($(filter $(P),$(MPI_PROGS)),)
	$(MPIRUN) $(MPIRUN_FLAGS) -np $(NP) $(OUT)/$(P) $(ARGS)
else
	$(OUT)/$(P) $(ARGS)
endif

clean:
	rm -rf $(OUT)

.PHONY: all run clean
