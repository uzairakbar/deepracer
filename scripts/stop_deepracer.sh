#!/bin/bash
set -e

export container=deepracer
docker stop "$container"

export image=deepracer
docker rmi "$image"