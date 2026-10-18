#include <algorithm> // sort
#include <cassert>   // assert
#include <math.h>    // sqrtf
#include <omp.h>     // OpenMP
#include <stdlib.h>  // rand
#include "Trip.h"

using namespace std;

// --------------------------------------------------------------------------
// City names and indexes
// --------------------------------------------------------------------------

/*
 * Converts a city name to its index in coordinates: 'A'-'Z' -> 0-25, '0'-'9' -> 26-35.
 */
int city_to_index(char city)
{
  int c = city;

  /*
   * c >> 6 is 1 for letters (ASCII 65-90) and 0 for digits (ASCII 48-57).
   * Letters subtract 22 + 43 = 65 ('A'), so 'A' -> 0.
   * Digits subtract only 22 ('0' - 26), so '0' -> 26.
   */
  return c - 22 - ((c >> 6) * 43);
}

/*
 * Converts an index from 0 to 35 back to its city name. Inverse of city_to_index().
 */
char index_to_city(int index)
{
  if (index < 26)
  {
    // Maps 0-25 to 'A'-'Z' (ASCII 65-90)
    return 'A' + index;
  }
  else
  {
    // Maps 26-35 to '0'-'9' (ASCII 48-57)
    return '0' + (index - 26);
  }
}

/*
 * Returns a random city name.
 */
char get_random_city()
{
  return index_to_city(rand() % CITIES);
}

/*
 * Returns a random city that is not yet marked in visited.
 */
char find_unvisited_city(const bool visited[CITIES])
{
  char new_city = get_random_city();

  while (visited[city_to_index(new_city)])
  {
    new_city = get_random_city();
  }

  return new_city;
}

// --------------------------------------------------------------------------
// Coordinates and distance
// --------------------------------------------------------------------------

/*
 * Returns the Euclidean distance between two (x, y) points.
 */
float calculate_distance(int x1, int y1, int x2, int y2)
{
  int dx = x2 - x1;
  int dy = y2 - y1;
  return sqrtf(dx * dx + dy * dy);
}

/*
 * Returns the distance between two cities.
 */
float city_distance(char from, char to, const int coordinates[CITIES][2])
{
  int from_index = city_to_index(from);
  int x1 = coordinates[from_index][0];
  int y1 = coordinates[from_index][1];

  int to_index = city_to_index(to);
  int x2 = coordinates[to_index][0];
  int y2 = coordinates[to_index][1];

  return calculate_distance(x1, y1, x2, y2);
}

/*
 * Returns the distance from the starting point (0, 0) to a city.
 */
float origin_distance(char city, const int coordinates[CITIES][2])
{
  int index = city_to_index(city);
  return calculate_distance(0, 0, coordinates[index][0], coordinates[index][1]);
}

// --------------------------------------------------------------------------
// Itinerary helpers for crossover
// --------------------------------------------------------------------------

/*
 * Returns the city that follows city in itinerary, wrapping to the
 * first city if city is the last one.
 */
char next_city_in_trip(char city, const char itinerary[CITIES + 1])
{
  for (int i = 0; i < CITIES; i++)
  {
    if (itinerary[i] == city)
    {
      return itinerary[(i + 1) % CITIES];
    }
  }

  assert(false && "City is unexpectedly missing from the itinerary!");
  return '\0';
}

/*
 * Fills offspring2 with the complement of offspring1. The city at index k is
 * replaced by the city at index CITIES - 1 - k, so A <-> 9, B <-> 8, and so on.
 */
void crossover_complement(const char offspring1[CITIES + 1], char offspring2[CITIES + 1])
{
  for (int i = 0; i < CITIES; i++)
  {
    char city = offspring1[i];
    int complement = CITIES - 1 - city_to_index(city);
    offspring2[i] = index_to_city(complement);
  }
}

// --------------------------------------------------------------------------
// Genetic algorithm steps called from Tsp.cpp
// --------------------------------------------------------------------------

/*
 * Evaluates each trip (or chromosome) and sort them out
 */
void evaluate(Trip trip[CHROMOSOMES], int coordinates[CITIES][2])
{
  for (int i = 0; i < CHROMOSOMES; i++)
  {
    const char *itinerary = trip[i].itinerary;

    double total = 0.0; // double to avoid summation error
    total += origin_distance(itinerary[0], coordinates);

    for (int j = 1; j < CITIES; j++)
    {
      char prev_city = itinerary[j - 1];
      char current_city = itinerary[j];
      total += city_distance(prev_city, current_city, coordinates);
    }

    trip[i].fitness = total;
  }

  sort(trip, trip + CHROMOSOMES, [](const Trip &lhs, const Trip &rhs)
       { return lhs.fitness < rhs.fitness; });
}

/*
 * Generates new TOP_X offsprings from TOP_X parents.
 * Note that the i-th and (i+1)-th offsprings are created from the i-th and (i+1)-th parents
 */
void crossover(Trip parents[TOP_X], Trip offsprings[TOP_X], int coordinates[CITIES][2])
{
  for (int i = 0; i < TOP_X; i += 2)
  {
    bool visited[CITIES] = {false};

    const char *parent1 = parents[i].itinerary;
    const char *parent2 = parents[i + 1].itinerary;
    char *offspring1 = offsprings[i].itinerary;
    char *offspring2 = offsprings[i + 1].itinerary;

    offspring1[0] = parent1[0];

    for (int j = 1; j < CITIES; j++)
    {
      char current_city = offspring1[j - 1];
      visited[city_to_index(current_city)] = true;

      char parent1_next = next_city_in_trip(current_city, parent1);
      bool parent1_next_visited = visited[city_to_index(parent1_next)];

      char parent2_next = next_city_in_trip(current_city, parent2);
      bool parent2_next_visited = visited[city_to_index(parent2_next)];

      // Spec: If both cities are visited, select an unvisited city at random.
      if (parent1_next_visited && parent2_next_visited)
      {
        offspring1[j] = find_unvisited_city(visited);
      }
      // Spec: If one city is visited, select the other one.
      else if (parent1_next_visited)
      {
        offspring1[j] = parent2_next;
      }
      else if (parent2_next_visited)
      {
        offspring1[j] = parent1_next;
      }
      // Spec: If neither city is visited, select the closer one.
      else
      {
        float parent1_next_distance = city_distance(current_city, parent1_next, coordinates);
        float parent2_next_distance = city_distance(current_city, parent2_next, coordinates);

        if (parent1_next_distance <= parent2_next_distance)
        {
          offspring1[j] = parent1_next;
        }
        else
        {
          offspring1[j] = parent2_next;
        }
      }
    }

    crossover_complement(offspring1, offspring2);
    offspring1[CITIES] = '\0';
    offspring2[CITIES] = '\0';
  }
}

/*
 * Mutate a pair of genes in each offspring.
 */
void mutate(Trip offsprings[TOP_X])
{
  for (int i = 0; i < TOP_X; i++)
  {
    bool should_mutate = (rand() % 100) < MUTATE_RATE;
    if (!should_mutate)
    {
      continue;
    }

    int gene1 = rand() % CITIES;

    int gene2;
    do
    {
      gene2 = rand() % CITIES;
    } while (gene2 == gene1);

    char temp = offsprings[i].itinerary[gene1];
    offsprings[i].itinerary[gene1] = offsprings[i].itinerary[gene2];
    offsprings[i].itinerary[gene2] = temp;
  }
}
