#!/bin/bash
export container=deepracer
docker rm "$container"

export image=deepracer
docker image rm -f "$image"

export base=uzairakbar/deepracer:v0
docker image rm -f "$base"

docker system prune --force

export conda_env=deepracer
conda activate base
conda remove --name "$conda_env" --all --yes