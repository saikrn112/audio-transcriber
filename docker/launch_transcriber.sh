#!/bin/bash
# Launch transcriber container for audio-transcriber project
# Usage: bash launch_transcriber.sh [optional docker run args]

CONTAINER_NAME="transcriber"
IMAGE_NAME="transcriber:v2"
FSX_CACHE="/fsx/users/${USER}/.cache"
WORKSPACE="/fsx/users/${USER}/workspace/audio-transcriber"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build image if it doesn't exist
if ! docker image inspect ${IMAGE_NAME} &>/dev/null; then
    echo "Building ${IMAGE_NAME}..."
    docker build -t ${IMAGE_NAME} -f ${SCRIPT_DIR}/Dockerfile.transcriber-v2 ${SCRIPT_DIR}
fi

# Create cache dirs if needed
mkdir -p ${FSX_CACHE}/{uv,conda/pkgs}
mkdir -p ${WORKSPACE}/data/{uploads,transcripts,stats}

docker run \
    --gpus all \
    --ipc=host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    --name ${CONTAINER_NAME} \
    -v ${WORKSPACE}:/workspace \
    -v ${FSX_CACHE}/uv:/root/.cache/uv \
    -v ${FSX_CACHE}/conda/pkgs:/opt/conda/pkgs \
    -e UV_CACHE_DIR=/root/.cache/uv \
    -e CONDA_PKGS_DIRS=/opt/conda/pkgs \
    -e USE_GPU=1 \
    -it \
    "$@" \
    ${IMAGE_NAME}
