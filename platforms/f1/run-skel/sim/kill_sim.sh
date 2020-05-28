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

if [ ! -z "$(screen -ls | grep bootcheck)" ]
then
	screen -X -S bootcheck quit
fi

