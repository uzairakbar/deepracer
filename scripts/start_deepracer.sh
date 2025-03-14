#!/bin/bash
set -x

helpFunction()
{
    echo ""
    echo "Usage: $0 -C CPUs -M memory"
    echo -e "\t-C Maximum CPUs to allocate to the container, e.g. \"3\"."
    echo -e "\t-M Maximum memory to allocate to the container, e.g. \"6g\"."
    exit 1 # Exit script after printing help
}

while getopts "C:M:" opt
do
    case "$opt" in
        C ) cpus="$OPTARG" ;;
        M ) memory="$OPTARG" ;;
        ? ) helpFunction ;; # Print helpFunction in case parameter is non-existent
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
docker pull "$base"

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
