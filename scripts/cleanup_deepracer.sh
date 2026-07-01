#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

export base=uzairakbar/deepracer-test:v0
export container=deepracer
export image=deepracer

# Same scratch resolution as start_deepracer.sh: $SCRATCH, else ~/scratch, else cwd.
if [ -n "$SCRATCH" ]; then
    SCRATCH_DIR="$SCRATCH"
elif [ -d "$HOME/scratch" ]; then
    SCRATCH_DIR="$HOME/scratch"
else
    SCRATCH_DIR="$PWD"
fi

# load uv via environment modules if available (common on HPC clusters)
if command_exists module; then
    module load uv 2>/dev/null || true
fi

# check for Apptainer
if command_exists apptainer; then

    rm -f "$SCRATCH_DIR"/"$image".sif
    rm -f deepracer.sif deepracer.sif.tmp
    overlay=/tmp/"$container"_overlay
    rm -rf "$overlay"

    echo "Cleaned deepracer Apptainer environment."

# check for Docker
elif command_exists docker; then
    
    docker rm "$container"

    docker image rm -f "$image"

    docker image rm -f "$base"

    docker system prune --force

    echo "Cleaned deepracer Docker environment."
fi

# check for UV
if command_exists uv; then
    
    # remove local venv
    if [ -d ".venv" ] || [ -L ".venv" ]; then
        rm -rf .venv
    fi
    
    # remove the per-project uv env under scratch
    if [ -d "$SCRATCH_DIR/uv_envs/deepracer" ]; then
        rm -rf "$SCRATCH_DIR/uv_envs/deepracer"
    fi

    # clear the uv cache
    if [ -d "$SCRATCH_DIR/.cache/uv" ]; then
        rm -rf "$SCRATCH_DIR/.cache/uv"
    fi

    # delete lockfile for fresh re-builds
    if [ -f "uv.lock" ]; then
        rm -f uv.lock
    fi

    echo "Cleaned deepracer UV environment."
fi

# no environment found to clean
echo "Nothing more to clean!"