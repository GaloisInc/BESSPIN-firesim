#!/bin/bash
# Start firesim docker container with proper settings to enable local builds

base_dir=$(pwd)

DOCKER_CONTAINER=firesim_runtime

DOCKER_OPTS=(-it)
DOCKER_OPTS+=(-e FIRESIM_HOST_PATH=${base_dir})
DOCKER_OPTS+=(-v $base_dir:/firesim)
DOCKER_OPTS+=(-v /var/run/docker.sock:/var/run/docker.sock)
if [ ! -z ${SSH_AUTH_SOCK+x} ]
then
  DOCKER_OPTS+=(-v $(readlink -f $SSH_AUTH_SOCK):/ssh-agent -e SSH_AUTH_SOCK=/ssh-agent)
fi

sudo docker run "${DOCKER_OPTS[@]}" $DOCKER_CONTAINER bash
