CXX      ?= g++
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra -fopenmp
OUT       = ../out

$(OUT)/main: main.cpp
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ $<

run: $(OUT)/main
	$(OUT)/main $(ARGS)

clean:
	rm -rf $(OUT)

.PHONY: run clean
