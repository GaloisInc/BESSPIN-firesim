#!/bin/bash

if [ ! -z "$(screen -ls | grep fsim0)" ]
then
	screen -X -S fsim0 quit
fi

if [ ! -z "$(screen -ls | grep switch0)" ]
then
	screen -X -S switch0 quit
fi

sudo rm -rf /dev/shm/*

# Clear SSH known_hosts if it exists
if [ -f ~/.ssh/known_hosts ]
then
	sed -i '/172\.16\.0\.2/d' ~/.ssh/known_hosts
fi

if [ ! -z "$(screen -ls | grep bootcheck)" ]
then
	screen -X -S bootcheck quit
fi

