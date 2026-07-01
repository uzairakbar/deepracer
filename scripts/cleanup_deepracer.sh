#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# check if on a PACE ICE machine
on_pace_ice() {
    local var="$1"
    if [[ "$var" == *pace.gatech.edu ]]; then
        return 0  # Success (matches)
    else
        return 1  # Failure (does not match)
    fi
}

export base=uzairakbar/deepracer-test:v0
export container=deepracer
export image=deepracer

SCRATCH_DIR=''
if on_pace_ice "$(hostname)"; then
    SCRATCH_DIR="$HOME"/scratch
    module load uv
else
    SCRATCH_DIR="$PWD"
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
    
    # remove the scratch dir in PACE
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