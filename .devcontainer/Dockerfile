FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    make \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with sudo access
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install Python tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install direnv
RUN curl -sfL https://direnv.net/install.sh | bash

# Add direnv hook to .bashrc
RUN echo 'eval "$(direnv hook bash)"' >> /home/$USERNAME/.bashrc

# Install project dependencies
WORKDIR /workspace
COPY pyproject.toml ./
COPY README.md ./
COPY setup.py ./

# Prevent Python from writing bytecode files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensure console output is unbuffered
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER $USERNAME

# Add .local/bin to PATH
ENV PATH="${PATH}:/home/${USERNAME}/.local/bin"

# Install pre-commit
RUN pip install --user pre-commit

CMD ["bash"]
