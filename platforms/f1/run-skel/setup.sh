#!/bin/bash
#
# One time setup script for F1 instances
#
# On initial run, it'll install aws-fpga tools. On subsequent runs, it'll only refresh kernel modules. Useful when restarting the same instance.

die() { echo "$*" 1>&2; exit 1; }

base_dir=$(pwd)

if [ ! -f /usr/bin/fpga-load-local-image ]
then
	echo "Getting AWS FPGA SDK"
	git clone https://github.com/aws/aws-fpga || die "Cloning FPGA SDK failed"
	cd aws-fpga && git checkout 6c707ab4a26c2766b916dad9d40727266fa0e4ef
	source sdk_setup.sh || die "Building FPGA SDK failed..."
	cd ..
fi

# Just try removing all modules anyway.. no harm
sudo rmmod xocl &> /dev/null
sudo rmmod xdma &> /dev/null
sudo rmmod edma &> /dev/null
sudo rmmod nbd  &> /dev/null

echo "Loading kernel modules"
sudo insmod kmods/nbd.ko nbds_max=128
sudo insmod kmods/xdma.ko poll_mode=1

echo "Setup done!"
