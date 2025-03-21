#!/bin/bash

export container=deepracer
docker stop "$container"

sleep 5

export image=deepracer
docker rmi "$image"