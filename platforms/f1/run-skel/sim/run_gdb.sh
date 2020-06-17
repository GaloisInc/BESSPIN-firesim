#!/bin/bash
#
# This script will automatically checkout riscv-tools if you
# don't have them, setup your environment, and run gdb with 
# a given ELF file (if provided)

function die() {
	echo "Error. Exiting.."
	exit 1
}

if [ -z ${RISCV+x} ]
then
	export RISCV=~/riscv-tools-install
fi

if [ ! -d $RISCV ]
then
	echo "RISCV Tools not installed in expected location. Installing now..."
	if [ ! -f ~/cloudgfe-riscv-toolchain.tgz ]
	then
		aws s3 cp s3://firesim-localuser/swpkgs/cloudgfe-riscv-toolchain.tgz ~/cloudgfe-riscv-toolchain.tgz || die
	else
		echo "Found an existing tgz. Using it."
	fi		
	tar xzf ~/cloudgfe-riscv-toolchain.tgz -C ~ || die
	echo "Installed!"
fi

which riscv64-unknown-elf-gdb > /dev/null
RET=$?

if [ "$RET" != "0" ]
then
	export PATH=$RISCV/bin:$PATH
fi

echo "Starting gdb"
mkdir -p logs
riscv64-unknown-elf-gdb -x init.gdb $1
