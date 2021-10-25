FROM nvcr.io/nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

LABEL maintainer "Daniel Bershatsky <daniel.bershatsky@gmail.com>"

# Set up default timezone.

ENV TZ=Europe/Moscow

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Install common packages.

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        neovim \
        python3 \
        python3-pip \
        python3.9 \
        python3.9-venv && \
    rm -rf /var/lib/apt/lists/*

# Set up workspace directory to non-root user.

WORKDIR /workspace

ARG LOGIN=developer

ARG UID=1000

RUN useradd -m -U -u $UID $LOGIN && \
    chown -R $LOGIN /workspace

USER $LOGIN

# Install required Python packages into virtual env.

ENV PATH="/home/$LOGIN/.local/bin:$PATH"

RUN python3.9 -m venv /home/$LOGIN/.local && \
    . /home/$LOGIN/.local/bin/activate && \
    pip install \
        ipython \
        jupyter \
        jupytext \
        matplotlib \
        numpy \
        scipy \
        wheel && \
    pip install \
        "jax[cuda111]" \
        -f "https://storage.googleapis.com/jax-releases/jax_releases.html" && \
    rm -rf /home/$LOGIN/.cache
