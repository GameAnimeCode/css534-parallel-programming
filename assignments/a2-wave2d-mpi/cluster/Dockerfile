# One node of the local MPI test cluster. compose.yaml starts four of these on
# a private network with the repository mounted at /workspace, so mpiexec on
# node1 launches ranks on node2..node4 over SSH, the way the cssmpi machines do.
# The build context is the repository root (see compose.yaml and
# .containerignore) so the MPICH install script is shared with .devcontainer.
#
# Everything inside a node runs as root. With rootless podman that is your own
# user on the host, so files written to /workspace stay yours.
FROM registry.fedoraproject.org/fedora:44

RUN dnf install -y \
  gcc-c++ make \
  openssh-server openssh-clients \
  hostname procps-ng && \
  dnf clean all

# MPICH2 1.2.1p1 at the cssmpi prefix, with the hydra launcher.
COPY .devcontainer/install-mpich121.sh /tmp/install-mpich121.sh
RUN /tmp/install-mpich121.sh && rm /tmp/install-mpich121.sh
ENV PATH="/usr/apps/mpich121-x86_64/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/apps/mpich121-x86_64/lib"

# SSH: host keys, one shared root key so every node accepts every other node,
# and no host-key prompts. hydra starts its remote proxies through these
# logins, and ~/.ssh/environment gives those non-interactive shells the PATH.
RUN ssh-keygen -A && \
  mkdir -p -m 700 /root/.ssh && \
  ssh-keygen -q -N "" -t ed25519 -f /root/.ssh/id_ed25519 && \
  cp /root/.ssh/id_ed25519.pub /root/.ssh/authorized_keys && \
  printf 'Host *\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  LogLevel ERROR\n' \
  > /root/.ssh/config && \
  printf 'PATH=/usr/apps/mpich121-x86_64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin\nLD_LIBRARY_PATH=/usr/apps/mpich121-x86_64/lib\n' \
  > /root/.ssh/environment && \
  chmod 600 /root/.ssh/* && \
  printf 'PermitRootLogin prohibit-password\nPasswordAuthentication no\nPermitUserEnvironment yes\n' \
  > /etc/ssh/sshd_config.d/10-mpi.conf

COPY assignments/a2-wave2d-mpi/cluster/hostfile /etc/mpi/hostfile

WORKDIR /workspace
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
