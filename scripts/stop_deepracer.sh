#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

export container=deepracer
export image=deepracer

# check for Apptainer
if command_exists apptainer; then

    apptainer instance stop "$container" || echo "No ${container} instance running."

    overlay=/tmp/"$container"_overlay
    rm -rf "$overlay"

    echo "Stopped deepracer Apptainer container."

# check for Docker
elif command_exists docker; then
    
    docker stop "$container"

    echo "Stopped deepracer Docker container."

else

    # if neither Docker nor Apptainer is found
    echo "Neither Docker nor Apptainer is installed"

fi