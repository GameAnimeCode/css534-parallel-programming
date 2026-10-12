#include <iostream>  // cout
#include <stdlib.h>  // rand
#include <math.h>    // sqrt, pow
#include <omp.h>     // OpenMP
#include <string.h>  // memset
#include "Timer.h"
#include "Trip.h"

#define CHROMOSOMES    50000 // 50000 different trips
#define CITIES         36    // 36 cities = ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
#define TOP_X          25000 // top optimal 25%
#define MUTATE_RATE    50    // optimal 50%

using namespace std;

/*
 * Evaluates each trip (or chromosome) and sort them out
 */
void evaluate( Trip trip[CHROMOSOMES], int coordinates[CITIES][2] ) {

}

/*
 * Generates new TOP_X offsprings from TOP_X parents.
 * Noe that the i-th and (i+1)-th offsprings are created from the i-th and (i+1)-th parents
 */
void crossover( Trip parents[TOP_X], Trip offsprings[TOP_X], int coordinates[CITIES][2] ) {

}

/*
 * Mutate a pair of genes in each offspring.
 */
void mutate( Trip offsprings[TOP_X] ) {

}

