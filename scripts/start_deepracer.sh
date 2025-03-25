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

while getopts "C:M:" opt
do
    case "$opt" in
        C ) cpus="$OPTARG" ;;
        M ) memory="$OPTARG" ;;
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
logs=logs/deepracer

mkdir -p "$logs"
mkdir -p "$configs"
mkdir -p "$patches"

export base=uzairakbar/deepracer:v0
export container=deepracer
export image=deepracer

# check for Docker
if command_exists docker; then
    echo "Building deepracer Docker container."
    
    docker pull "$base"
    docker build -t "$image" .

    docker system prune --force

    docker run --rm --detach \
        --name="$container" \
        -v "$PWD"/"$logs":/"$logs" \
        -p 8888:8888 -p 5000:5000 \
        --cpus="$cpus" --memory="$memory" \
        "$image" \
        /bin/bash
    
    echo "Started deepracer Docker container."

fi

# check for Apptainer
if command_exists apptainer; then
    echo "Building deepracer Apptainer container."

    apptainer pull deepracer_base.sif docker://"$base"

    apptainer build --ignore-fakeroot-command "$image".sif deepracer.def

    overlay=/tmp/"$container"_overlay
    rm -rf "$overlay" && mkdir "$overlay"
    apptainer instance run \
        --no-mount "$HOME",/tmp,/dev,/etc/hosts,/etc/localtime,/proc,/sys,/var/tmp \
        --bind configs:/configs \
        --overlay "$overlay"/:/. \
        "$image".sif "$container" \
        --cpus="$cpus" --memory="$memory"
    
    # apptainer instance run \
    #     --compact \
    #     --workdir /tmp \
    #     --bind configs:/configs \
    #     "$image".sif "$container" \
    #     --cpus="$cpus" --memory="$memory"

    echo "Started deepracer Apptainer container."

fi

# if neither Docker nor Apptainer is found
echo "Neither Docker nor Apptainer is installed"
