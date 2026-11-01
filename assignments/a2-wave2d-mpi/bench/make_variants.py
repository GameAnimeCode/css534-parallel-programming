#!/usr/bin/env python3
"""Generate one source folder per benchmark variant from ../src/Wave2D_mpi.cpp.

The time loop body is cut into its boundary, post, interior and wait parts, and
each x_ variant puts them back together with one change. Those variants are
timed: they add MPI_Wtime calls around the parts and print a PHASES line per
rank, so a run reports its exchange time directly instead of as a slice of the
total. Output goes to build/variants/, which is gitignored.

  no_omp    the code in src/ with the omp pragma removed, not timed
  x_overlap the code in src/, timed
  x_async   every row computes first, then the same Isend, Irecv and Waitall
  x_left    blocking exchange after the compute, odd ranks left first
  x_right   blocking, odd ranks right first (the chain)
  x_before  x_left with the exchange before the compute, as handout item (3) orders it
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src" / "Wave2D_mpi.cpp"
OUT = HERE / "build" / "variants"

BOUNDARY_MARK = "    // Compute the boundary rows first so they can be sent right away\n"
POST_MARK = "    // Swap boundary rows with both neighbors\n"
INTERIOR_MARK = "    // Compute the interior rows while the messages travel\n"
WAIT_MARK = "    // Wait for the ghost rows before the next step reads them\n"
LOOP_END = "  } // end of simulation\n"
LOOP_START = "  for (int t = 2; t < max_time; t++)\n"
TIMER_START = "  // time = 0;\n"
TIMER_END = "  // finish the timer\n"
ODD_BRANCH = "    else\n    {\n"
INTERIOR_LOOP = "    for (int i = stripe_begin + 1; i < stripe_end; i++)\n"
ALL_ROWS_LOOP = "    for (int i = stripe_begin; i <= stripe_end; i++)\n"

# The exchange as it was before the overlap, in the same shape: odd ranks go left first.
BLOCKING = """    if (my_rank % 2 == 0)
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
"""


def swap(text, old, new, count=1):
    """Replace a snippet that must appear exactly `count` times."""
    found = text.count(old)
    if found != count:
        raise SystemExit(f"expected {count} matches, found {found}: {old!r}")
    return text.replace(old, new)


def split(source):
    """Cut the source into head, boundary, post, interior, wait and tail."""
    for mark in (BOUNDARY_MARK, POST_MARK, INTERIOR_MARK, WAIT_MARK, LOOP_END):
        swap(source, mark, mark)
    head, rest = source.split(BOUNDARY_MARK)
    boundary, rest = rest.split(POST_MARK)
    post, rest = rest.split(INTERIOR_MARK)
    interior, rest = rest.split(WAIT_MARK)
    wait, tail = rest.split(LOOP_END)
    return head, BOUNDARY_MARK + boundary, POST_MARK + post, INTERIOR_MARK + interior, WAIT_MARK + wait, LOOP_END + tail


def right_first(exchange):
    """Swap the two blocks of the odd branch, so odd ranks start on their right."""
    swap(exchange, ODD_BRANCH, ODD_BRANCH)
    even, odd = exchange.split(ODD_BRANCH)
    body = odd[:odd.rindex("    }\n")]
    swap(body, "      }\n      if (", "      }\n      if (")
    left, right = body.split("      }\n      if (")
    return even + ODD_BRANCH + "      if (" + right + left + "      }\n    }\n"


def timed(index, text, name):
    return (f"    double prof_t{index} = MPI_Wtime();\n" + text
            + f"    prof_{name} += MPI_Wtime() - prof_t{index};\n")


def assemble(head, parts, tail):
    """Rebuild the program with a timer around each (text, "compute" or "exchange") part."""
    head = swap(head, "#include <stdlib.h> // atoi\n", "#include <stdio.h>\n#include <stdlib.h> // atoi\n")
    head = swap(head, TIMER_START, "  double prof_start = MPI_Wtime();\n" + TIMER_START)
    head = swap(head, LOOP_START,
                "  double prof_compute = 0.0, prof_exchange = 0.0;\n"
                "  double prof_init = MPI_Wtime() - prof_start;\n" + LOOP_START)
    tail = swap(tail, TIMER_END,
                # One fprintf, because ranks writing with cerr interleave mid-line.
                "  fprintf(stderr, \"PHASES rank=%d init=%g compute=%g exchange=%g total=%g\\n\",\n"
                "          my_rank, prof_init, prof_compute, prof_exchange, MPI_Wtime() - prof_start);\n\n"
                + TIMER_END)
    return head + "".join(timed(i, text, name) for i, (text, name) in enumerate(parts)) + tail


def main():
    source = SRC.read_text()
    head, boundary, post, interior, wait, tail = split(source)
    compute = swap(interior, INTERIOR_LOOP, ALL_ROWS_LOOP)
    right = right_first(BLOCKING)
    blocking = lambda exchange: assemble(head, [(compute, "compute"), (exchange, "exchange")], tail)
    variants = {
        "no_omp": swap(source, "#pragma omp parallel for\n", ""),
        "x_overlap": assemble(head, [(boundary, "compute"), (post, "exchange"), (interior, "compute"),
                                     (wait, "exchange")], tail),
        "x_async": assemble(head, [(compute, "compute"), (post + wait, "exchange")], tail),
        "x_left": blocking(BLOCKING),
        "x_right": blocking(right),
        # Before the compute the rows to send are the previous step's.
        "x_before": assemble(head, [(swap(BLOCKING, "z_curr[", "z[t_prev][", 8), "exchange"),
                                    (compute, "compute")], tail),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in variants.items():
        folder = OUT / name
        folder.mkdir(exist_ok=True)
        (folder / "Wave2D_mpi.cpp").write_text(text)
    print(f"wrote {len(variants)} variants to {OUT.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
