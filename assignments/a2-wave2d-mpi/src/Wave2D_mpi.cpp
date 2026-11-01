#include "Timer.h"
#include <iostream> // i/o
#include <math.h>   // pow
#include <mpi.h>    // mpi
#include <omp.h>    // omp
#include <stdlib.h> // atoi

int default_size = 100; // the default system size
int defaultCellWidth = 8;
double c = 1.0;  // wave speed
double dt = 0.1; // time quantum
double dd = 2.0; // change in system

using namespace std;

// Find the first and last row of a rank's stripe.
// First ranks get extra rows.
void find_stripe(int rank, int size, int mpi_size, int &begin, int &end)
{
  int stripe = size / mpi_size;
  int remainder = size % mpi_size;

  begin = rank * stripe + (rank < remainder ? rank : remainder);
  end = begin + stripe - (rank < remainder ? 0 : 1);
}

// Compute one row for t >= 2.
// Zt_i,j = 2.0 * Zt-1_i,j - Zt-2_i,j + c^2 * (dt/dd)^2 * (Zt-1_i+1,j +
// Zt-1_i-1,j + Zt-1_i,j+1 + Zt-1_i,j-1 - 4.0 * Zt-1_i,j)
void compute_row(double *curr, const double *prev, const double *prev2,
                 int size, double constant)
{
  const double *prev_up = prev + size;
  const double *prev_down = prev - size;

  for (int j = 1; j < size - 1; j++)
  {
    curr[j] = 2.0 * prev[j] - prev2[j] +
              constant * (prev_up[j] + prev_down[j] + prev[j + 1] +
                          prev[j - 1] - 4.0 * prev[j]);
  }
}

// Async send and receive, ghost boundary rows.
void async_send_recv(double *send_row, double *ghost_row, int neighbor,
                     int size, MPI_Request *requests)
{
  MPI_Irecv(ghost_row, size, MPI_DOUBLE, neighbor, 0, MPI_COMM_WORLD,
            &requests[0]);
  MPI_Isend(send_row, size, MPI_DOUBLE, neighbor, 0, MPI_COMM_WORLD,
            &requests[1]);
}

// Print one frame in the format Wout reads.
void print_frame(int t, const double *grid, int size)
{
  cout << t << endl;
  for (int j = 0; j < size; j++)
  {
    for (int i = 0; i < size; i++)
      cout << grid[i * size + j] << " ";
    cout << endl;
  }
  cout << endl;
}

int main(int argc, char *argv[])
{
  // verify arguments
  if (argc != 5)
  {
    cerr << "usage: Wave2D_mpi size max_time interval threads" << endl;
    return -1;
  }

  int size = atoi(argv[1]);
  int max_time = atoi(argv[2]);
  int interval = atoi(argv[3]);
  int threads = atoi(argv[4]);

  if (size < 100 || max_time < 3 || interval < 0 || threads < 1)
  {
    cerr << "usage: Wave2D_mpi size max_time interval threads" << endl;
    cerr << "       where size >= 100 && time >= 3 && interval >= 0 && "
            "threads >= 1"
         << endl;
    return -1;
  }

  // Set the OpenMP thread count for this rank
  omp_set_num_threads(threads);

  // Start MPI
  int my_rank = 0;
  int mpi_size = 1;

  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &my_rank);
  MPI_Comm_size(MPI_COMM_WORLD, &mpi_size);

  // Rows each rank sends to rank 0 for printing
  int counts[mpi_size];
  int displacements[mpi_size];

  for (int rank = 0; rank < mpi_size; rank++)
  {
    int rank_begin = 0;
    int rank_end = 0;
    find_stripe(rank, size, mpi_size, rank_begin, rank_end);

    counts[rank] = (rank_end - rank_begin + 1) * size;
    displacements[rank] = rank_begin * size;
  }

  // Find this rank's stripe
  int stripe_begin = 0;
  int stripe_end = 0;
  find_stripe(my_rank, size, mpi_size, stripe_begin, stripe_end);
  cerr << "rank[" << my_rank << "]'s range = " << stripe_begin << " ~ "
       << stripe_end << endl;

  // The i = 0 and i = size - 1 edges stay at 0, so skip them
  if (stripe_begin == 0)
  {
    stripe_begin = 1;
  }
  if (stripe_end == size - 1)
  {
    stripe_end -= 1;
  }

  // create a simulation space
  double z[3][size][size];
  for (int p = 0; p < 3; p++)
    for (int i = 0; i < size; i++)
      for (int j = 0; j < size; j++)
        z[p][i][j] = 0.0; // no wave

  // start a timer
  Timer time;
  if (my_rank == 0)
  {
    time.start();
  }

  // time = 0;
  // initialize the simulation space: calculate z[0][][]
  int weight = size / default_size;
  for (int i = 0; i < size; i++)
  {
    for (int j = 0; j < size; j++)
    {
      if (i > 40 * weight && i < 60 * weight && j > 40 * weight &&
          j < 60 * weight)
      {
        z[0][i][j] = 20.0;
      }
      else
      {
        z[0][i][j] = 0.0;
      }
    }
  }

  // time = 1
  // calculate z[1][][]
  // cells not on edge
  // Zt_i,j = Zt-1_i,j + c^2 / 2 * (dt/dd)^2 * (Zt-1_i+1,j + Zt-1_i-1,j +
  // Zt-1_i,j+1 + Zt-1_i,j-1 – 4.0 * Zt-1_i,j)
  const double constant_mp_t1 = pow(c, 2) / 2 * pow((dt / dd), 2);

  for (int i = 1; i < size - 1; i++)
  {
    for (int j = 1; j < size - 1; j++)
    {
      z[1][i][j] =
          z[0][i][j] +
          constant_mp_t1 * (z[0][i + 1][j] + z[0][i - 1][j] + z[0][i][j - 1] +
                            z[0][i][j + 1] - 4.0 * z[0][i][j]);
    }
  }

  // simulate wave diffusion from time = 2
  const double constant_mp_t2 = pow(c, 2) * pow((dt / dd), 2);

  for (int t = 2; t < max_time; t++)
  {
    const int t_prev = (t + 2) % 3;
    const int t_prev2 = (t + 1) % 3;
    double (*z_curr)[size] = z[t % 3];

    // Print before computing, so frame t holds time t - 3 as in out1.txt
    if (interval != 0 && (t % interval == 0 || t == max_time - 1))
    {
      void *send_start = my_rank == 0 ? MPI_IN_PLACE : z_curr[stripe_begin];
      MPI_Gatherv(send_start, counts[my_rank], MPI_DOUBLE,   // send
                  z_curr, counts, displacements, MPI_DOUBLE, // recv
                  0, MPI_COMM_WORLD);

      if (my_rank == 0)
      {
        print_frame(t, z_curr[0], size);
      }
    }

    // Compute the boundary rows first so they can be sent right away
    compute_row(z_curr[stripe_begin], z[t_prev][stripe_begin],
                z[t_prev2][stripe_begin], size, constant_mp_t2);
    compute_row(z_curr[stripe_end], z[t_prev][stripe_end],
                z[t_prev2][stripe_end], size, constant_mp_t2);

    // Swap boundary rows with both neighbors
    MPI_Request requests[4];
    int n_reqs = 0;

    if (my_rank > 0)
    {
      async_send_recv(z_curr[stripe_begin], z_curr[stripe_begin - 1],
                      my_rank - 1, size, &requests[n_reqs]);
      n_reqs += 2;
    }
    if (my_rank < mpi_size - 1)
    {
      async_send_recv(z_curr[stripe_end], z_curr[stripe_end + 1], my_rank + 1,
                      size, &requests[n_reqs]);
      n_reqs += 2;
    }

    // Compute the interior rows while the messages travel
#pragma omp parallel for
    for (int i = stripe_begin + 1; i < stripe_end; i++)
    {
      compute_row(z_curr[i], z[t_prev][i], z[t_prev2][i], size, constant_mp_t2);
    }

    // Wait for the ghost rows before the next step reads them
    MPI_Waitall(n_reqs, requests, MPI_STATUSES_IGNORE);
  } // end of simulation

  // finish the timer
  if (my_rank == 0)
  {
    cerr << "Elapsed time = " << time.lap() << endl;
  }

  // Shut down MPI
  MPI_Finalize();
  return 0;
}
