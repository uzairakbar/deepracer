#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

export container=deepracer
export image=deepracer

# check for Docker
if command_exists docker; then
    
    docker stop "$container"
    sleep 3
    docker rmi "$image"

    echo "Stopped deepracer Docker container."
    
fi

# check for Apptainer
if command_exists apptainer; then

    apptainer instance stop "$container"
    sleep 3

    echo "Stopped deepracer Apptainer container."

fi

# if neither Docker nor Apptainer is found
echo "Neither Docker nor Apptainer is installed"
