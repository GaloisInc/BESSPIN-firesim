#!/usr/bin/env bash

firesim_dir=$(pwd)/..
cd ${firesim_dir}
git submodule update --init sim
git submodule update --init target-design/chipyard

cd target-design/chipyard
git submodule update --init --recursive generators
git submodule update --init --recursive tools

cd ${firesim_dir}/sim
export FIRESIM_STANDALONE=1
export FIRESIM_ENV_SOURCED=1
make publish-scala-doc JVM_MEMORY=700M
