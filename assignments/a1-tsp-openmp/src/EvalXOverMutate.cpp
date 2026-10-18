#include <algorithm>     // sort
#include <math.h>        // sqrtf
#include <omp.h>         // OpenMP
#include <stdlib.h>      // rand
#include <unordered_set> // set
#include "Trip.h"

using namespace std;

int city_to_index(char city)
{
  int c = city;
  /*
   * Maps 'A'-'Z' -> 0-25  |  '0'-'9' -> 26-35
   * Avoids branch prediction penalties by using bit 6 as a multiplier switch.
   * If c is a number (ASCII < 64), shift is 0 -> subtracts 22.
   * If c is a letter (ASCII > 64), shift is 1 -> subtracts 65 (22 + 43).
   */
  return c - 22 - ((c >> 6) * 43);
}

pair<int, int> get_city_coordinates(char city, int coordinates[CITIES][2])
{
  int index = city_to_index(city);
  return {coordinates[index][0], coordinates[index][1]};
}

int position_in_trip(char city, char itinerary[CITIES + 1])
{
  for (int i = 0; i < CITIES; i++)
  {
    if (itinerary[i] == city)
    {
      return i;
    }
  }

  return -1; // Should never happen
}

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

char get_random_city()
{
  return index_to_city(rand() % CITIES);
}

// Euclidean Distance
float calculate_distance(pair<int, int> x1y1, pair<int, int> x2y2)
{
  int dx = x2y2.first - x1y1.first;
  int dy = x2y2.second - x1y1.second;
  return sqrtf(dx * dx + dy * dy);
}

void crossover_complement(char offspring1[CITIES + 1], char offspring2[CITIES + 1])
{
  for (int i = 0; i < CITIES; i++)
  {
    char city = offspring1[i];
    int complement = CITIES - 1 - city_to_index(city);
    offspring2[i] = index_to_city(complement);
  }
}

/*
 * Evaluates each trip (or chromosome) and sort them out
 */
void evaluate(Trip trip[CHROMOSOMES], int coordinates[CITIES][2])
{
  for (int i = 0; i < CHROMOSOMES; i++)
  {
    char *itinerary = trip[i].itinerary;

    double total = 0.0; // double to avoid summation error
    total += calculate_distance({0, 0}, get_city_coordinates(itinerary[0], coordinates));

    for (int j = 1; j < CITIES; j++)
    {
      char prev_city = itinerary[j - 1];
      auto prev_city_coords = get_city_coordinates(prev_city, coordinates);

      char current_city = itinerary[j];
      auto current_city_coords = get_city_coordinates(current_city, coordinates);

      total += calculate_distance(prev_city_coords, current_city_coords);
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
    unordered_set<char> visited;

    auto find_unvisited_city = [&visited]() -> char
    {
      char new_city;
      bool found = false;

      do
      {
        new_city = get_random_city();
        if (visited.find(new_city) == visited.end())
        {
          found = true;
        }
      } while (!found);

      return new_city;
    };

    char *parent1 = parents[i].itinerary;
    char *parent2 = parents[i + 1].itinerary;
    char *offspring1 = offsprings[i].itinerary;
    char *offspring2 = offsprings[i + 1].itinerary;

    offspring1[0] = parent1[0];

    for (int j = 1; j < CITIES; j++)
    {
      char current_city = offspring1[j - 1];
      visited.insert(current_city);

      int next_city1_pos = (position_in_trip(current_city, parent1) + 1) % CITIES;
      char next_city1 = parent1[next_city1_pos];
      bool next_city1_visited = visited.find(next_city1) != visited.end();

      int next_city2_pos = (position_in_trip(current_city, parent2) + 1) % CITIES;
      char next_city2 = parent2[next_city2_pos];
      bool next_city2_visited = visited.find(next_city2) != visited.end();

      if (next_city1_visited && next_city2_visited)
      {
        offspring1[j] = find_unvisited_city();
      }
      else if (!next_city1_visited && next_city2_visited)
      {
        offspring1[j] = next_city1;
      }
      else if (!next_city2_visited && next_city1_visited)
      {
        offspring1[j] = next_city2;
      }
      else
      {
        auto current_city_coords = get_city_coordinates(current_city, coordinates);

        auto next_city1_coords = get_city_coordinates(next_city1, coordinates);
        float next_city1_distance = calculate_distance(current_city_coords, next_city1_coords);

        auto next_city2_coords = get_city_coordinates(next_city2, coordinates);
        float next_city2_distance = calculate_distance(current_city_coords, next_city2_coords);

        if (next_city1_distance <= next_city2_distance)
        {
          offspring1[j] = next_city1;
        }
        else
        {
          offspring1[j] = next_city2;
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
