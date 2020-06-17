#!/bin/bash

BLKIMG=$1
DWARF_FILE=$2
ELF_FILE=$3

AGFI=FIRESIM_AGFI
CONFIG=FIRESIM_CONFIG

# Tracing Support
#
# You can dump a processor trace (PC + instruction) to a text file for debugging.
# Set the TRACE_START and TRACE_END parameters below to specify which cycles you'd
# like to capture. This WILL slow down your simulation, and the trace files become
# very large quickly. So it should be used sparingly. You will also need to add
# `+tracefile0=TRACEFILE` to the FireSim-f1 argument list at the end of this file

TRACE_START=0
TRACE_END=1

# Debugger Support
#
# You can connect gdb to this simulator via a custom version of OpenOCD.
#
# To download the toolchain, run:
# aws s3 cp s3://firesim-localuser/cloudgfe-riscv-toolchain.tgz .
#
# Then extract it to ~/riscv-tools-install
#
# When you enable debug below, the simulator will wait until gdb is connected.
# The ELF file provided to this script will still be pre-loaded into memory, making
# it unnecessary to run `load` within gdb to start. Use the provided init.gdb script
# along with openocd.cfg to connect. The pc will be set to main memory by init.gdb

DEBUG_ENABLE=0

if [ -z $BLKIMG ] || [ -z $DWARF_FILE ] || [ -z $ELF_FILE ]
then
	echo "ERROR: Please specify correct arguments"
	echo "$0 <blockimage> <dwarf> <elf>"
	exit -1
fi

DEBUG_ARGS=""
if [ "$DEBUG_ENABLE" == "1" ]
then
	DEBUG_ARGS="+debug_enable"
fi	

echo "Checking Network Config"
if [ -z "$(sudo ip link show | grep tap)" ]
then
	echo "Creating tap interface"
	sudo ip tuntap add mode tap dev tap0 user $USER
	sudo ip link set tap0 down
	sudo ip addr add 172.16.0.1/16 dev tap0
	sudo ifconfig tap0 hw ether 8e:6b:35:04:00:00
	sudo sysctl -w net.ipv6.conf.tap0.disable_ipv6=1
	
	echo "Starting NAT"
	sudo sysctl -w net.ipv4.ip_forward=1
	export EXT_IF_TO_USE=$(ifconfig -a | sed 's/[ \t].*//;/^\(lo:\|\)$/d' | sed 's/[ \t].*//;/^\(tap0:\|\)$/d' | sed 's/://g')
	sudo iptables -A FORWARD -i $EXT_IF_TO_USE -o tap0 -m state --state RELATED,ESTABLISHED -j ACCEPT
	sudo iptables -A FORWARD -i tap0 -o $EXT_IF_TO_USE -j ACCEPT
	sudo iptables -t nat -A POSTROUTING -o $EXT_IF_TO_USE -j MASQUERADE
else
	echo "Bringing tap interface down"
	sudo ifconfig tap0 hw ether 8e:6b:35:04:00:00
	sudo ip link set tap0 down
fi

echo "Clearing FPGA Slot"
sudo fpga-clear-local-image -S 0
echo "Programming FPGA with $CONFIG"
sudo fpga-load-local-image -S 0 -I $AGFI

if [ -z "$(screen -ls | grep switch)" ]
then
	echo "Starting switch"
	screen -S switch0 -d -m bash -c "script -f -c 'sudo ./switch0 6405 10 200' switchlog0"
else
	echo "Switch already running"
fi

if [ ! -z "$(screen -ls | grep bootcheck)" ]
then
	echo "Killing stale bootcheck"
	screen -X -S bootcheck quit
fi

echo "Starting bootcheck"
touch uartlog
screen -S bootcheck -d -m bash -c "tail -f uartlog | grep -q 'Welcome' && sudo ip link set dev tap0 up"

echo "Starting simulation"
screen -S fsim0 -m bash -c "script -f -c 'stty intr ^] && sudo LD_LIBRARY_PATH=.:$LD_LIBRARY_PATH ./FireSim-f1 \
+permissive \
+mm_relaxFunctionalModel=0 \
+mm_openPagePolicy=1 \
+mm_backendLatency=2 \
+mm_schedulerWindowSize=8 \
+mm_transactionQueueDepth=8 \
+mm_dramTimings_tAL=0 \
+mm_dramTimings_tCAS=14 \
+mm_dramTimings_tCMD=1 \
+mm_dramTimings_tCWD=10 \
+mm_dramTimings_tCCD=4 \
+mm_dramTimings_tFAW=25 \
+mm_dramTimings_tRAS=33 \
+mm_dramTimings_tREFI=7800 \
+mm_dramTimings_tRC=47 \
+mm_dramTimings_tRCD=14 \
+mm_dramTimings_tRFC=160 \
+mm_dramTimings_tRRD=8 \
+mm_dramTimings_tRP=14 \
+mm_dramTimings_tRTP=8 \
+mm_dramTimings_tRTRS=2 \
+mm_dramTimings_tWR=15 \
+mm_dramTimings_tWTR=8 \
+mm_rowAddr_offset=18 \
+mm_rowAddr_mask=65535 \
+mm_rankAddr_offset=16 \
+mm_rankAddr_mask=3 \
+mm_bankAddr_offset=13 \
+mm_bankAddr_mask=7 \
+mm_llc_wayBits=3 \
+mm_llc_setBits=12 \
+mm_llc_blockBits=7 \
+mm_llc_activeMSHRs=8 \
${DEBUG_ARGS} \
+slotid=0 \
+profile-interval=-1 \
+macaddr0=00:12:6D:00:00:02 \
+blkdev0=${BLKIMG} \
+niclog0=niclog0 \
+blkdev-log0=blkdev-log0 \
+trace-select0=1 \
+trace-start0=${TRACE_START} \
+trace-end0=${TRACE_END} \
+trace-output-format0=0 \
+dwarf-file-name0=${DWARF_FILE} \
+autocounter-readrate0=0 \
+autocounter-filename0=AUTOCOUNTERFILE0 \
+linklatency0=6405 \
+netbw0=200 \
+shmemportname0=0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000 \
+permissive-off ${ELF_FILE} && stty intr ^c' uartlog; sleep 1"
