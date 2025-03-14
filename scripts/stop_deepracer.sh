#!/bin/bash
set -x
export container=deepracer
docker stop "$container"
export image=deepracer
docker rmi "$image"