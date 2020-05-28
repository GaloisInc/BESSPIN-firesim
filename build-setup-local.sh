#!/usr/bin/env bash

# Local version of firesim setup script. This assumes you have access to (or have built your own) docker images

# FireSim initial setup script. This script will:
# 1) Initalize submodules (only the required ones, minimizing duplicates

# exit script if any command fails
set -e
set -o pipefail

unamestr=$(uname)
RISCV=$(pwd)/riscv-tools-install
RDIR=$(pwd)

if [ -f firesim-setup-complete ]
then
  echo "Setup has already been completed. If you really want to run this script, remove ./firesim-setup-complete first."
  return
fi

git config submodule.target-design/chipyard.update none
git submodule update --init --recursive #--jobs 8

# This checks if firemarshal has already been configured by someone. If
# not, we will provide our own config. This must be checked before calling
# init-submodules-no-riscv-tools.sh because that will configure
# firemarshal.
marshal_cfg=$RDIR/target-design/chipyard/software/firemarshal/marshal-config.yaml
if [ ! -f $marshal_cfg ]; then
  first_init=true
else
  first_init=false
fi

git config --unset submodule.target-design/chipyard.update
git submodule update --init target-design/chipyard
cd $RDIR/target-design/chipyard
./scripts/init-submodules-no-riscv-tools.sh --no-firesim
cd $RDIR

# Configure firemarshal to know where our firesim installation is.
# If this is a fresh init of chipyard, we can safely overwrite the marshal
# config, otherwise we have to assume the user might have changed it
if [ $first_init = true ]; then
  echo "firesim-dir: '../../../../'" > $marshal_cfg
fi

target_chipyard_dir=$RDIR/target-design/chipyard

# setup marshal symlink
ln -sf ../target-design/chipyard/software/firemarshal $RDIR/sw/firesim-software

#generate env.sh file which sources the chipyard env.sh file
echo "if [ -z ${FIRESIM_ENV_SOURCED+x} ]; then " > env.sh
echo "  if [ -f \"$target_chipyard_dir/env.sh\" ]; then" >> env.sh
echo "    source $target_chipyard_dir/env.sh" >> env.sh
echo "    export FIRESIM_ENV_SOURCED=1" >> env.sh
echo "  else" >> env.sh
echo "    echo \"Error: You may have forgot to build or source the toolchains (build them independently in firesim-as-a-library mode)\"" >> env.sh
echo "  fi" >> env.sh
echo "fi" >> env.sh
echo "export FIRESIM_STANDALONE=1" >> env.sh
echo "export FIRESIM_PREFIX=$FIRESIM_PREFIX" >> env.sh
echo "export FIRESIM_LOCAL=1" >> env.sh

cd $RDIR

# Install firesim-software dependencies
# We always setup the symlink correctly above, so use sw/firesim-software
marshal_dir=$RDIR/sw/firesim-software

cd $RDIR
bash sourceme-f1-full.sh

touch firesim-setup-complete
echo "Setup complete!"
