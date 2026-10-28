#!/usr/bin/env bash
# Local MPI test cluster: four containers (node1..node4) on a private network
# with this repository mounted at /workspace, standing in for cssmpi machines.
# Works from inside the devcontainer (through the host's podman socket) or
# from the host.
#
# Usage:
#   cluster.sh up                      build the image and start the nodes
#   cluster.sh down                    stop and remove the nodes
#   cluster.sh status                  list the nodes
#   cluster.sh ssh [nodeN]             shell on a node (default node1)
#   cluster.sh exec nodeN cmd...       run a command on a node
#   cluster.sh mpirun -np 4 ../out/Wave2D_mpi 100 500 10 4
#                                      mpirun on node1 across all nodes
#
# ssh, exec, and mpirun run in the node's copy of your current directory, so
# call them from src/ or lab/ with the same relative paths you use locally.
# mpirun is MPICH2 1.2.1p1's hydra mpiexec with "-f /etc/mpi/hostfile", which
# places ranks round-robin over the nodes like the mpd ring on cssmpi.
# MPIRUN_FLAGS replaces that default. CSS534_HOST_WORKSPACE overrides the
# detected host path of the repository.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
compose_file="$here/compose.yaml"
project="css534-mpi"

die() { echo "cluster.sh: $*" >&2; exit 1; }

# Path of the repository on the host, for the bind mount. Inside the
# devcontainer the repository is itself a bind mount, and /proc/self/mountinfo
# records where it came from.
host_repo() {
  if [[ -n "${CSS534_HOST_WORKSPACE:-}" ]]; then
    printf '%s' "$CSS534_HOST_WORKSPACE"
    return
  fi
  local src
  src="$(awk -v m="$repo" '$5 == m { print $4; exit }' /proc/self/mountinfo)"
  printf '%s' "${src:-$repo}"
}

# Current directory as seen inside a node.
node_cwd() {
  case "$PWD" in
    "$repo") printf '/workspace' ;;
    "$repo"/*) printf '/workspace%s' "${PWD#"$repo"}" ;;
    *) printf '/workspace' ;;
  esac
}

compose() {
  if command -v podman-compose >/dev/null 2>&1; then
    CSS534_HOST_WORKSPACE="$(host_repo)" podman-compose -p "$project" -f "$compose_file" "$@"
  elif docker compose version >/dev/null 2>&1; then
    CSS534_HOST_WORKSPACE="$(host_repo)" docker compose -p "$project" -f "$compose_file" "$@"
  else
    die "need podman-compose or docker compose"
  fi
}

engine() {
  if command -v podman >/dev/null 2>&1; then podman "$@"; else docker "$@"; fi
}

node_name() {
  local n="${1:-node1}"
  [[ "$n" =~ ^node[1-4]$ ]] || die "node must be node1..node4, got '$n'"
  printf 'css534-%s' "$n"
}

run_in() {
  local node="$1"; shift
  local tty=()
  [[ -t 0 && -t 1 ]] && tty=(-t)
  engine exec -i "${tty[@]}" -w "$(node_cwd)" "$node" "$@"
}

cmd="${1:-}"
[[ -n "$cmd" ]] || { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
shift

case "$cmd" in
  up)
    echo "mounting $(host_repo) at /workspace in each node"
    compose up -d --build "$@"
    ;;
  down)
    compose down "$@"
    ;;
  status)
    engine ps --filter name='^css534-node' --format 'table {{.Names}}\t{{.Status}}'
    ;;
  ssh)
    run_in "$(node_name "${1:-node1}")" bash -l
    ;;
  exec)
    [[ $# -ge 2 ]] || die "usage: cluster.sh exec nodeN cmd..."
    node="$(node_name "$1")"; shift
    run_in "$node" "$@"
    ;;
  mpirun)
    # shellcheck disable=SC2086
    run_in "$(node_name node1)" /usr/apps/mpich121-x86_64/bin/mpiexec \
      ${MPIRUN_FLAGS--f /etc/mpi/hostfile} "$@"
    ;;
  *)
    die "unknown command '$cmd'"
    ;;
esac
