#!/bin/bash

# check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# kill process at specified port
kill_port() {
    local PORT=$1

    if [ -z "$PORT" ]; then
        echo "Usage: kill_port <port_number>"
        return 1
    fi

    local PID
    PID=$(lsof -ti tcp:$PORT)

    if [ -n "$PID" ]; then
        echo "Port $PORT is in use by process ID $PID. Killing it..."
        kill -9 $PID
        echo "Process $PID has been killed."
    else
        echo "Port $PORT is not in use."
    fi
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

sleep 2

# just make sure nothing is running
kill_port 8888