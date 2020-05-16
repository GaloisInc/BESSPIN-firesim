# you should source this only if you plan to run build/simulations locally,
# without using the manager at all.

unamestr=$(uname)
RDIR=$(pwd)
AWSFPGA=$RDIR/platforms/f1/aws-fpga

# setup risc-v tools
source ./env.sh

# setup AWS tools
cd $AWSFPGA
if [ "$FIRESIM_LOCAL" == "1" ]
then
	echo "Executing HDK setup inside docker"
	sudo docker run -v $RDIR:/firesim artifactory.galois.com:5008/firesim:bitstream_gen bash -c 'cd /firesim/platforms/f1/aws-fpga; source ./hdk_setup.sh'
else
	source ./hdk_setup.sh
	source ./sdk_setup.sh
fi
export CL_DIR=$AWSFPGA/hdk/cl/developer_designs/cl_firesim
cd $RDIR

# put the manager on the user path
export PATH=$PATH:$(pwd)/deploy

# setup ssh-agent
# source deploy/ssh-setup.sh

# flag for scripts to check that this has been sourced
export FIRESIM_SOURCED=1
