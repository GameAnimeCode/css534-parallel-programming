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

  // Init MPI
  int my_rank = 0;
  int mpi_size = 1;

  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &my_rank);
  MPI_Comm_size(MPI_COMM_WORLD, &mpi_size);

  // Calculate stipe size and determine stripe start and end
  int stripe = size / mpi_size;
  int remainder = size % mpi_size;
  int stripe_begin = 0;
  int stripe_end = 0;
  if (my_rank < remainder)
  {
    stripe_begin = my_rank * (stripe + 1);
    // stripe_begin + (stripe + 1) - 1 = stripe_begin + stripe
    stripe_end = stripe_begin + stripe;
  }
  else
  {
    stripe_begin = my_rank * stripe + remainder;
    stripe_end = stripe_begin + stripe - 1;
  }

  // Shift stipe begin and end for edges
  if (stripe_begin == 0)
  {
    stripe_begin = 1;
  }
  if (stripe_end == size - 1)
  {
    stripe_end -= 1;
  }

  // Rank 0 gather setup
  int counts[mpi_size];
  int displacements[mpi_size];

  for (int i = 0; i < mpi_size; i++)
  {
    int rank_begin = i * stripe + (i < remainder ? i : remainder);
    int rank_end = rank_begin + stripe + (i < remainder ? 1 : 0);

    counts[i] = (rank_end - rank_begin) * size;
    displacements[i] = rank_begin * size;

    if (i == my_rank)
    {
      cerr << "rank[" << i << "]'s range = " << rank_begin << " ~ "
           << rank_end - 1 << endl;
    }
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
  // Zt_i,j = 2.0 * Zt-1_i,j - Zt-2_i,j + c^2 * (dt/dd)^2 * (Zt-1_i+1,j +
  // Zt-1_i-1,j + Zt-1_i,j+1 + Zt-1_i,j-1 - 4.0 * Zt-1_i,j)
  const double constant_mp_t2 = pow(c, 2) * pow((dt / dd), 2);

  for (int t = 2; t < max_time; t++)
  {
    const int t_prev = (t + 2) % 3;
    const int t_prev2 = (t + 1) % 3;
    double (*z_curr)[size] = z[t % 3];

    if (interval != 0 && (t % interval == 0 || t == max_time - 1))
    {
      // Grab all the data
      void *buffer_start = my_rank == 0 ? MPI_IN_PLACE : z_curr[stripe_begin];
      MPI_Gatherv(buffer_start, counts[my_rank], MPI_DOUBLE, // send
                  z_curr, counts, displacements, MPI_DOUBLE, // recv
                  0, MPI_COMM_WORLD);

      if (my_rank == 0)
      {
        cout << t << endl;
        for (int j = 0; j < size; j++)
        {
          for (int i = 0; i < size; i++)
            cout << z_curr[i][j] << " ";
          cout << endl;
        }
        cout << endl;
      }
    }

#pragma omp parallel for
    for (int i = stripe_begin; i <= stripe_end; i++)
    {
      double *curr = z_curr[i];
      const double *prev = z[t_prev][i];
      const double *prev_up = z[t_prev][i + 1];
      const double *prev_down = z[t_prev][i - 1];
      const double *prev2 = z[t_prev2][i];

      for (int j = 1; j < size - 1; j++)
      {
        curr[j] = 2.0 * prev[j] - prev2[j] +
                  constant_mp_t2 * (prev_up[j] + prev_down[j] + prev[j + 1] +
                                    prev[j - 1] - 4.0 * prev[j]);
      }
    }

    // Swap ghost stripes
    if (my_rank % 2 == 0)
    {
      if (my_rank < mpi_size - 1)
      {
        double *send_buff = z_curr[stripe_end];
        double *recv_buff = z_curr[stripe_end + 1];

        MPI_Send(send_buff, size, MPI_DOUBLE, my_rank + 1, 0, MPI_COMM_WORLD);
        MPI_Recv(recv_buff, size, MPI_DOUBLE, my_rank + 1, 0, MPI_COMM_WORLD,
                 MPI_STATUS_IGNORE);
      }
      if (my_rank > 0)
      {
        double *send_buff = z_curr[stripe_begin];
        double *recv_buff = z_curr[stripe_begin - 1];

        MPI_Send(send_buff, size, MPI_DOUBLE, my_rank - 1, 0, MPI_COMM_WORLD);
        MPI_Recv(recv_buff, size, MPI_DOUBLE, my_rank - 1, 0, MPI_COMM_WORLD,
                 MPI_STATUS_IGNORE);
      }
    }
    else
    {
      if (my_rank > 0)
      {
        double *send_buff = z_curr[stripe_begin];
        double *recv_buff = z_curr[stripe_begin - 1];

        MPI_Recv(recv_buff, size, MPI_DOUBLE, my_rank - 1, 0, MPI_COMM_WORLD,
                 MPI_STATUS_IGNORE);
        MPI_Send(send_buff, size, MPI_DOUBLE, my_rank - 1, 0, MPI_COMM_WORLD);
      }
      if (my_rank < mpi_size - 1)
      {
        double *send_buff = z_curr[stripe_end];
        double *recv_buff = z_curr[stripe_end + 1];

        MPI_Recv(recv_buff, size, MPI_DOUBLE, my_rank + 1, 0, MPI_COMM_WORLD,
                 MPI_STATUS_IGNORE);
        MPI_Send(send_buff, size, MPI_DOUBLE, my_rank + 1, 0, MPI_COMM_WORLD);
      }
    }
  } // end of simulation

  // finish the timer
  if (my_rank == 0)
  {
    cerr << "Elapsed time = " << time.lap() << endl;
  }

  // Flush MPI
  MPI_Finalize();
  return 0;
}
