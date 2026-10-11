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
  openmpi openmpi-devel \
  java-25-openjdk-devel \
  openssh-clients rsync \
  docker podman podman-compose \
  wget gnupg curl git \
  zsh tmux vim powerline powerline-fonts tmux-powerline vim-powerline && \
  dnf clean all

# Fedora installs OpenMPI outside the default path; expose mpicc, mpicxx, and mpirun.
ENV PATH="/usr/lib64/openmpi/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/lib64/openmpi/lib"
ENV JAVA_HOME=/usr/lib/jvm/java-25-openjdk

# Install Quarto and TinyTeX to render the markdown writeups to PDF.
# librsvg2-tools provides rsvg-convert, which Quarto needs to embed SVG figures in PDF output.
ARG QUARTO_VERSION=1.10.19
USER root
RUN dnf install -y librsvg2-tools && \
  curl -fsSL -o /tmp/quarto.rpm \
  "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-$(uname -m).rpm" && \
  dnf install -y /tmp/quarto.rpm && \
  rm /tmp/quarto.rpm && \
  dnf clean all
USER vscode
RUN quarto install tinytex --no-prompt

# Install Oh My Zsh, Powerlevel10k, and ZSH plugins manually
RUN git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git /home/vscode/.oh-my-zsh && \
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/vscode/.oh-my-zsh/custom/themes/powerlevel10k && \
  git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions /home/vscode/.oh-my-zsh/custom/plugins/zsh-autosuggestions && \
  git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting.git /home/vscode/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting

USER root
