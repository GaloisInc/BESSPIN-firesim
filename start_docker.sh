#!/bin/bash
# Start firesim docker container with proper settings to enable local builds

base_dir=$(pwd)

DOCKER_CONTAINER=artifactory.galois.com:5008/firesim:runtime

DOCKER_OPTS=(-it)
DOCKER_OPTS+=(-e FIRESIM_HOST_PATH=${base_dir})
DOCKER_OPTS+=(-v $base_dir:/firesim)
DOCKER_OPTS+=(-v /var/run/docker.sock:/var/run/docker.sock)
if [ ! -z ${SSH_AUTH_SOCK+x} ]
then
  DOCKER_OPTS+=(-v $(readlink -f $SSH_AUTH_SOCK):/ssh-agent -e SSH_AUTH_SOCK=/ssh-agent)
fi
if [ ! -z ${AWS_ACCESS_KEY_ID+z} ]
then
  # Assume the other keys are set too
  # But check for the region
  if [ -z ${AWS_DEFAULT_REGION+x} ]
  then
     AWS_DEFAULT_REGION="us-west-2"
     echo "WARN: Setting default AWS region to \"$AWS_DEFAULT_REGION\". If this is incorrect, set the correct region in AWS_DEFAULT_REGION"
  fi
  DOCKER_OPTS+=(-e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" -e AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION)
fi

sudo docker run "${DOCKER_OPTS[@]}" $DOCKER_CONTAINER bash
