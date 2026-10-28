FROM registry.fedoraproject.org/fedora:44

# Create a non-root user matching the default host UID (1000)
# This provides VS Code a valid home directory (/home/vscode) to install its server
RUN groupadd --gid 1000 vscode && \
  useradd --uid 1000 --gid 1000 -m -s /bin/bash vscode

# Install Dev Tools, Container CLI clients, and the C++/Java/MPI toolchains
RUN dnf config-manager addrepo --from-repofile https://cli.github.com/packages/rpm/gh-cli.repo && \
  dnf update -y && \
  dnf install -y \
  gh \
  python3 python3-pip \
  gcc-c++ make gdb \
  java-25-openjdk-devel \
  openssh-clients rsync \
  docker podman podman-compose \
  wget gnupg curl git \
  zsh tmux vim powerline powerline-fonts tmux-powerline vim-powerline && \
  dnf clean all

# MPICH2 1.2.1p1 at the cssmpi prefix, so mpic++, mpirun, headers, and
# libraries match the course cluster (see install-mpich121.sh).
COPY install-mpich121.sh /tmp/install-mpich121.sh
RUN /tmp/install-mpich121.sh && rm /tmp/install-mpich121.sh
ENV PATH="/usr/apps/mpich121-x86_64/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/apps/mpich121-x86_64/lib"
# hydra launches local ranks with fork; the cluster script passes a hostfile.
ENV HYDRA_BOOTSTRAP=fork
ENV JAVA_HOME=/usr/lib/jvm/java-25-openjdk

# Install and setup Quarto to render the markdown writeups to PDF.
ARG QUARTO_VERSION=1.10.19
USER root
RUN dnf install -y librsvg2-tools perl-File-Find && \
  curl -fsSL -o /tmp/quarto.rpm \
  "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-$(uname -m).rpm" && \
  dnf install -y /tmp/quarto.rpm && \
  rm /tmp/quarto.rpm && \
  dnf clean all
USER vscode
RUN quarto install tinytex --no-prompt && \
  ~/.TinyTeX/bin/*/tlmgr update --self && \
  ~/.TinyTeX/bin/*/tlmgr install pgfplots lm luatexbase

# Install Oh My Zsh, Powerlevel10k, and ZSH plugins manually
RUN git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git /home/vscode/.oh-my-zsh && \
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/vscode/.oh-my-zsh/custom/themes/powerlevel10k && \
  git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions /home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions && \
  git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting.git /home/vscode/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting

USER root
