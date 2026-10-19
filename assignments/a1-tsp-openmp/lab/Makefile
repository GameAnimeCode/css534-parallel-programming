CXX      ?= g++
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra -Wno-unused-parameter
OUT       = ../out/lab

PROGS = pi_monte pi_monte_omp pi_integral pi_integral_omp

# Program to run, for example P=pi_monte_omp. The programs read the
# iteration count from stdin and take no arguments, so ARGS sets the
# OpenMP thread count instead.
P    ?= pi_monte_omp
ARGS ?= 1

ifneq ($(filter run,$(MAKECMDGOALS)),)
ifeq ($(filter $(P),$(PROGS)),)
$(error P=$(P) is not one of: $(PROGS))
endif
endif

all: $(addprefix $(OUT)/,$(PROGS))

$(OUT)/%_omp: %_omp.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -fopenmp -o $@ $< Timer.cpp

$(OUT)/%: %.cpp Timer.cpp Timer.h
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ $< Timer.cpp

run: $(OUT)/$(P)
	OMP_NUM_THREADS=$(ARGS) $(OUT)/$(P)

clean:
	rm -rf $(OUT)

.PHONY: all run clean
