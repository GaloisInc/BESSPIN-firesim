#!/bin/bash

# This file should be run after setting up your firesim manager instance. It modifies
# some files deep down the submodule hierarchy to avoid having to fork the repos

function die() {
	echo "Could not find riscv-pk files. Did you fully setup your manager instance?"
	exit -1
}	

if [ ! -f target-design/chipyard/software/firemarshal/README.md ]
then
	die
else
	pushd target-design/chipyard/software/firemarshal
	git submodule update --init riscv-pk
	popd
fi

if [ -f target-design/chipyard/software/firemarshal/riscv-pk/bbl/bbl.lds ]
then
	echo "Patching riscv-pk/bbl/bbl.lds"
	sed -i 's/0x80000000/0xc0000000/' target-design/chipyard/software/firemarshal/riscv-pk/bbl/bbl.lds
else
	die
fi

if [ -f target-design/chipyard/software/firemarshal/riscv-pk/machine/uart.c ]
then
	echo "Patching riscv-pk/machine/uart.c"
	sed -i 's/= 868/= 27/' target-design/chipyard/software/firemarshal/riscv-pk/machine/uart.c
else
	die
fi

echo "Done."
