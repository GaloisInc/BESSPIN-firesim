#!/usr/bin/env bash

# FireSim initial setup script. This script will:
# 1) Initalize submodules (only the required ones, minimizing duplicates
# 2) Install RISC-V tools, including linux tools
# 3) Installs python requirements for firesim manager

# TODO: build FireSim linux distro here?

# exit script if any command fails
set -e
set -o pipefail

unamestr=$(uname)
RISCV=$(pwd)/riscv-tools-install
RDIR=$(pwd)

if [ -z "$FIRESIM_PREFIX" ]
then
    echo "ERROR: Set FIRESIM_PREFIX and re-run"
    exit -1
fi

FASTINSTALL=false
IS_LIBRARY=false
SUBMODULES_ONLY=false

function usage
{
    echo "usage: build-setup.sh [ fast | --fast] [--submodules-only] [--library]"
    echo "   fast: if set, pulls in a pre-compiled RISC-V toolchain for an EC2 manager instance"
    echo "   submodules-only: if set, skips toolchain handling (cloning or building)"
    echo "   library: if set, initializes submodules assuming FireSim is being used"
    echo "            as a library submodule"
}

if [ "$1" == "--help" -o "$1" == "-h" -o "$1" == "-H" ]; then
    usage
    exit 3
fi

while test $# -gt 0
do
   case "$1" in
        fast | --fast) # I don't want to break this api
            FASTINSTALL=true
            ;;
        --library)
            IS_LIBRARY=true;
            ;;
        --submodules-only)
            SUBMODULES_ONLY=true;
            ;;
        -h | -H | --help)
            usage
            exit
            ;;
        --*) echo "ERROR: bad option $1"
            usage
            exit 1
            ;;
        *) echo "ERROR: bad argument $1"
            usage
            exit 2
            ;;
    esac
    shift
done

git config submodule.target-design/chipyard.update none
git submodule update --init --recursive #--jobs 8

if [ "$IS_LIBRARY" = false ]; then
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
fi

if [ "$SUBMODULES_ONLY" = true ]; then
    # Only initialize submodules
    exit
fi

target_chipyard_dir=$RDIR/target-design/chipyard

# setup marshal symlink
ln -sf ../target-design/chipyard/software/firemarshal $RDIR/sw/firesim-software

# Build toolchain here if needed

#generate env.sh file which sources the chipyard env.sh file
echo "if [ -f \"$target_chipyard_dir/env.sh\" ]; then" > env.sh
echo "  source $target_chipyard_dir/env.sh" >> env.sh
echo "  export FIRESIM_ENV_SOURCED=1" >> env.sh
echo "else" >> env.sh
echo "  echo \"Error: You may have forgot to build or source the toolchains (build them independently in firesim-as-a-library mode)\"" >> env.sh
echo "fi" >> env.sh

if  [ "$IS_LIBRARY" = false ]; then
    echo "export FIRESIM_STANDALONE=1" >> env.sh
fi

echo "export FIRESIM_PREFIX=$FIRESIM_PREFIX" >> env.sh
echo "export FIRESIM_LOCAL=1" >> env.sh

cd $RDIR

# Install firesim-software dependencies
# We always setup the symlink correctly above, so use sw/firesim-software
marshal_dir=$RDIR/sw/firesim-software
cd $RDIR
sudo pip3 install -r $marshal_dir/python-requirements.txt
sudo pip2 install -r python2-requirements.txt
#cat $marshal_dir/centos-requirements.txt | sudo xargs yum install -y
#wget https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git/snapshot/e2fsprogs-1.45.4.tar.gz
#tar xvzf e2fsprogs-1.45.4.tar.gz
#cd e2fsprogs-1.45.4/
#mkdir build && cd build
#../configure
#make
#sudo make install
#cd ../..
#rm -rf e2fsprogs*

# Setup for using qcow2 images
#cd $RDIR
#./scripts/install-nbd-kmod.sh

# run sourceme-f1-full.sh once on this machine to build aws libraries and
# pull down some IP, so we don't have to waste time doing it each time on
# worker instances
cd $RDIR
bash sourceme-f1-full.sh

#cd $RDIR
#source env.sh && ./scripts/build-libelf.sh
#cd $RDIR
#source env.sh && ./scripts/build-libdwarf.sh


#cd $RDIR
#./gen-tags.sh

echo "Setup complete!"
echo "To generate simulator RTL and run sw-RTL simulation, source env.sh"
echo "To use the manager to deploy builds/simulations on EC2, source sourceme-f1-manager.sh to setup your environment."
echo "To run builds/simulations manually on this machine, source sourceme-f1-full.sh to setup your environment."
