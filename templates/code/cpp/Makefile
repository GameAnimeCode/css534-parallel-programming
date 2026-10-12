CXX      ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -fopenmp
OUT       = ../out

$(OUT)/main: main.cpp
	mkdir -p $(OUT)
	$(CXX) $(CXXFLAGS) -o $@ $<

clean:
	rm -rf $(OUT)

.PHONY: clean
