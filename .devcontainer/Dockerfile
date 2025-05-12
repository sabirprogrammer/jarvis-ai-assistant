FROM python:3.10-slim

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libportaudio2 \
    libespeak1 \
    libasound2-dev \
    portaudio19-dev \
    python3-pyqt6 \
    libqt6gui6 \
    libxcb-xinerama0 \
    libpulse0 \
    ssh \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install Python tools
RUN pip install --no-cache-dir \
    black \
    flake8 \
    pylint \
    mypy \
    pytest \
    pytest-cov \
    pytest-asyncio \
    pytest-qt \
    pre-commit \
    sphinx \
    sphinx-rtd-theme

# Create workspace directory
RUN mkdir -p /workspace
RUN chown -R $USERNAME:$USERNAME /workspace

# Switch to non-root user
USER $USERNAME

# Set up git configuration
RUN git config --global core.autocrlf input

# Set the default shell to bash
ENV SHELL /bin/bash

# Switch back to dialog for any ad-hoc use of apt-get
ENV DEBIAN_FRONTEND=dialog

# Set working directory
WORKDIR /workspace

# Create necessary directories for the application
RUN mkdir -p /workspace/data \
    /workspace/logs \
    /workspace/config \
    /workspace/tests \
    /workspace/docs

# Set up Python path
ENV PYTHONPATH=/workspace

# Install development dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install additional development tools
RUN pip install --no-cache-dir \
    ipython \
    jupyter \
    notebook \
    debugpy \
    coverage \
    tox \
    twine \
    build

# Setup git hooks
RUN git config --global init.templateDir ~/.git-template \
    && mkdir -p ~/.git-template/hooks \
    && pre-commit init-templatedir ~/.git-template

# Create convenience aliases
RUN echo 'alias ll="ls -la"' >> ~/.bashrc \
    && echo 'alias python=python3' >> ~/.bashrc \
    && echo 'alias pip=pip3' >> ~/.bashrc \
    && echo 'alias pytest="pytest -v"' >> ~/.bashrc \
    && echo 'alias coverage="coverage run -m pytest && coverage report"' >> ~/.bashrc

# Add scripts directory to PATH
ENV PATH="/workspace/scripts:${PATH}"

# Setup completion
RUN echo 'source /usr/share/bash-completion/bash_completion' >> ~/.bashrc

# Create a welcome message
RUN echo 'echo "Welcome to Jarvis AI Assistant Development Environment!"' >> ~/.bashrc \
    && echo 'echo "Python $(python --version)"' >> ~/.bashrc \
    && echo 'echo "Run ./scripts/setup_dev.py to initialize the development environment"' >> ~/.bashrc

# Ensure proper permissions
RUN sudo chown -R $USERNAME:$USERNAME /workspace

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
