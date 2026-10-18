CXX      ?= g++
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra -fopenmp
OUT       = ../out

SRCS = Tsp.cpp EvalXOverMutate.cpp Timer.cpp
HDRS = Trip.h Timer.h

$(OUT)/Tsp: $(SRCS) $(HDRS)
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ $(SRCS)

run: $(OUT)/Tsp
	$(OUT)/Tsp $(ARGS)

clean:
	rm -rf $(OUT)

.PHONY: run clean
