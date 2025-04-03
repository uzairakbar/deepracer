#!/bin/bash

helpFunction()
{
    echo ""
    echo "Usage: $0 -C CPUs -M memory"
    echo -e "\t-C Maximum CPUs to allocate to the container, e.g. \"3\"."
    echo -e "\t-M Maximum memory to allocate to the container, e.g. \"6g\"."
    exit 1 # Exit script after printing help
}

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

while getopts "C:M:E:W:" opt
do
    case "$opt" in
        C ) cpus="$OPTARG" ;;
        M ) memory="$OPTARG" ;;
        E ) evaluation="$OPTARG" ;;
        W ) world_name="$OPTARG" ;;
        ? ) helpFunction ;; # print helpFunction in case parameter is non-existent
    esac
done

# assign default if empty
if [ -z "$cpus" ] || [ -z "$memory" ]
then
    cpus="${cpus:=3}"
    memory="${memory:=6g}"
    echo "Capping deepracer at ${cpus} CPUs and ${memory} memory.";
fi

patches=patches
configs=configs

mkdir -p "$configs"
mkdir -p "$patches"

export base=uzairakbar/deepracer:v0
export container=deepracer
export image=deepracer

SCRATCH_DIR=''
if on_pace_ice "$HOSTNAME"; then
    SCRATCH_DIR="$HOME"/scratch
    
    # if [ -L "$HOME"/.conda ]; then
    #     echo "Conda already in scratch directory."
    # else
    #     mv "$HOME"/.conda "$SCRATCH_DIR"/.conda
    #     ln "$HOME"/.conda "$SCRATCH_DIR"/.conda
    #     echo "Moved conda to scratch directory."
    # fi
    
else
    SCRATCH_DIR="$PWD"
fi

# check for Docker
if command_exists docker; then
    echo "Building deepracer Docker container."
    
    docker pull "$base"
    docker build -t "$image" .

    docker system prune --force

    docker run --rm --detach \
        --name="$container" \
        -v "$PWD"/"$configs":/"$configs":ro \
        -p 8888:8888 -p 5000:5000 \
        -e EVALUATION="$evaluation" \
        -e EVAL_WORLD_NAME="$world_name" \
        --cpus="$cpus" --memory="$memory" \
        "$image"
    
    echo "Started deepracer Docker container."
# check for Apptainer
elif command_exists apptainer; then
    echo "Building deepracer Apptainer container."

    apptainer pull deepracer_base.sif docker://"$base"

    yes no | apptainer build --ignore-fakeroot-command "$SCRATCH_DIR"/"$image".sif deepracer.def

    overlay=/tmp/"$container"_overlay
    rm -rf "$overlay" && mkdir "$overlay"
    apptainer instance run \
        --no-mount "$HOME",/tmp,/dev,/etc/hosts,/etc/localtime,/proc,/sys,/var/tmp \
        --bind configs:/configs \
        --overlay "$overlay"/:/. \
        --env EVALUATION="$evaluation",EVAL_WORLD_NAME="$world_name" \
        "$SCRATCH_DIR"/"$image".sif "$container" \
        --cpus="$cpus" --memory="$memory"
    
    # apptainer instance run \
    #     --compact \
    #     --workdir /tmp \
    #     --bind configs:/configs \
    #     "$image".sif "$container" \
    #     --cpus="$cpus" --memory="$memory"

    echo "Started deepracer Apptainer container."
else
    # if neither Docker nor Apptainer is found
    echo "Neither Docker nor Apptainer is installed"
fi