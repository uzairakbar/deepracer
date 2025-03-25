#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}


export conda_env=deepracer

export base=uzairakbar/deepracer:v0
export container=deepracer
export image=deepracer


# check for Docker
if command_exists docker; then
    
    docker rm "$container"

    docker image rm -f "$image"

    docker image rm -f "$base"

    docker system prune --force

    echo "Cleaned deepracer Docker environment."

fi

# check for Apptainer
if command_exists apptainer; then

    rm -f "$image".sif
    overlay=/tmp/"$container"_overlay
    rm -rf "$overlay"

    echo "Cleaned deepracer Apptainer environment."

fi

# check for Conda
if command_exists conda; then

    conda activate base
    conda remove --name "$conda_env" --all --yes

    echo "Cleaned deepracer Conda environment."

fi

# no environment found to clean
echo "Nothing to clean!"