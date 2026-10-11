CXX      ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -fopenmp

main: main.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<

clean:
	rm -f main

.PHONY: clean
