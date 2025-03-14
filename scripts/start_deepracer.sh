#!/bin/bash
set -x
logs=logs
configs=configs
mkdir -p "$logs"
mkdir -p "$configs"
export image=deepracer
docker build -t "$image" .
export container=deepracer
docker run -it --rm \
    --name="$container" \
    -v "$PWD"/"$logs":/"$logs" \
    -p 8888:8888 -p 5000:5000 \
    --cpus="3" --memory="6g" \
    "$image" \
    /bin/bash
