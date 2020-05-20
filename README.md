# CloudGFE FireSim

## Contents

1. [What is FireSim?](#what-is-firesim)
2. [Getting Started](#getting-started)
    1. [Quick Setup](#quick-setup)
    2. [One-Time Setup](#one-time-setup)
    3. [Setup Manager](#setup-manager)
3. [Run Linux on Existing AFI](#run-linux-on-existing-afi)
4. [Build Your Own Image](#build-your-own-image)
5. [Notes and Future Additions](#notes-and-future-additions)

## What is FireSim?

FireSim is an [open-source](https://github.com/firesim/firesim) cycle-accurate
FPGA-accelerated full-system hardware simulation platform that runs on cloud FPGAs (Amazon EC2 F1).

In CloudGFE, FireSim is capable of running both Bluespec and Chisel based SSITH cores. There are two approaches for integrating your custom core, as described later.

The FireSim documentation is very good for learning the basics, but there have been some modifications to support CloudGFE.
If you'd like to learn more about FireSim, see here: https://docs.fires.im/. 
Another good overview (in video format) is our tutorial from the Chisel Community Conference on [YouTube](https://www.youtube.com/watch?v=S3OriQnJXYQ).

## Getting Started

This simple tutorial will guide you through setting up a FireSim manager instance, run a pre-built AFI (AWS FPGA Image), and build an AFI of our own.
It will assume you already have access to the AWS DARPA portal, are generally familiar with starting/stopping/logging into instances, and generating AWS key pairs.

### Quick Setup

There is now a quick-setup available that uses pre-built Linux/FreeBSD images along with prebuilt AFIs. For details, [see this README](https://gist.github.com/dhand-galois/9c41af3c10cb9cea2daf2ae1c9e2deed)

### One-Time Setup

There is a one-time setup step per user to generate your own firesim VPC and security group. These will be used by FireSim to group all your
instances together and maintain access across them.

First, pick your `FIRESIM_PREFIX`. It should be unique to you. This allows multiple users on the same AWS account to run FireSim.

Create a new keypair with the name `FIRESIM_PREFIX-firesim`. For example, if my `FIRESIM_PREFIX` is `hello`, my key name would be `hello-firesim`.

Next launch a new instance in the EC2 dashboard.
* Step 1: Choose AMI -> Use the `Amazon Linux 2 AMI` with `64-bit (x86)` selected.
* Step 2: Instance Type -> `t2.nano` is all we need for this step.
* Step 3: Instance Details -> Set `Network` to the `aws-controltower-VPC` option. Set `Subnet` to one of the `PublicSubnet` options, 
and ensure `Auto-assign Public IP` is set to `Enable`. All other options can stay at default values.
* Skip Steps 4-7: At this point you can just press the `Review and Launch` button.

At the final setup page, hit `Launch` and be sure to pick the key you just created (`FIRESIM_PREFIX-firesim`). Once your instance is up and running, use the public IP to login.

```
ssh -i $FIRESIM_PREFIX-firesim.pem ec2-user@<INSTANCE IP ADDR>
```

At the command prompt run:
```
aws configure
```
Enter the appropriate information. Default output format is `None`. Your session information can be found on [the DARPA portal](https://darpa-ssith.awsapps.com/start#/)
after clicking on "Command line or programmatic access". The configure script does not ask for a session token, so add that manually to your configuration:
```
echo "aws_session_token=<PASTE IN LONG STRING>" >> ~/.aws/credentials
```

Now run the follow. Be sure to update your `FIRESIM_PREFIX` variable:
```
export FIRESIM_PREFIX="YOUR_PREFIX_HERE"
sudo yum -y install python-pip git
sudo pip install boto3
git clone https://github.com/DARPA-SSITH-Demonstrators/firesim.git
cp firesim/scripts/aws-setup.py aws-setup.py
python aws-setup.py
```

Once the script finishes, you can terminate the instance.

### Setup Manager

The FireSim Manager instance is used to launch all builds and simulations. It is not actually an F1 instance itself.

On the EC2 dashboard, launch a new instance
* Step 1: Choose AMI -> Seach for the string `FPGA Developer AMI - 1.6.0`. There will be 2 results from **Community AMIs**. Select those results. Select the **1.6.0** developer AMI.
* Step 2: Instance Type -> `t3.xlarge` could be a reasonable trade-off - 4 vCPUs with 16GB of RAM. **Note** This instance is quite a bit slower than the recommended `c5.4xlarge`. Consider using the larger instance to get everything setup the first time. You'll likely save money as it is well over 2x faster.
* Step 3: Instance Details -> Select the `FIRESIM_PREFIX-firesim` Network VPC. The default subnet should be fine. It would be a good idea to select the `Enable Termination protection` option.
This prevents others from terminating your instance (and losing all your data). Deselect the `T2/T3 Unlimited` option. In the `User data` field, copy/paste the script below into the box:
```
#!/bin/bash
echo "machine launch script started" > /home/centos/machine-launchstatus
sudo yum install -y mosh
sudo yum groupinstall -y "Development tools"
sudo yum install -y gmp-devel mpfr-devel libmpc-devel zlib-devel vim git java java-devel
curl https://bintray.com/sbt/rpm/rpm | sudo tee /etc/yum.repos.d/bintray-sbt-rpm.repo
sudo yum install -y sbt texinfo gengetopt
sudo yum install -y expat-devel libusb1-devel ncurses-devel cmake "perl(ExtUtils::MakeMaker)"
# deps for poky
sudo yum install -y python36 patch diffstat texi2html texinfo subversion chrpath git wget
# deps for qemu
sudo yum install -y gtk3-devel
# deps for firesim-software (note that rsync is installed but too old)
sudo yum install -y python36-pip python36-devel rsync
# Install GNU make 4.x (needed to cross-compile glibc 2.28+)
sudo yum install -y centos-release-scl
sudo yum install -y devtoolset-8-make

# install DTC. it's not available in repos in FPGA AMI
DTCversion=dtc-1.4.4
wget https://git.kernel.org/pub/scm/utils/dtc/dtc.git/snapshot/$DTCversion.tar.gz
tar -xvf $DTCversion.tar.gz
cd $DTCversion
make -j16
make install
cd ..
rm -rf $DTCversion.tar.gz
rm -rf $DTCversion

# get a proper version of git
sudo yum -y remove git
sudo yum -y install epel-release
sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
sudo yum -y install git2u

# install verilator
git clone http://git.veripool.org/git/verilator
cd verilator/
git checkout v4.028
autoconf && ./configure && make -j16 && sudo make install
cd ..

# bash completion for manager
sudo yum -y install bash-completion

# graphviz for manager
sudo yum -y install graphviz python-devel

# these need to match what's in deploy/requirements.txt
sudo pip2 install fabric==1.14.0
sudo pip2 install boto3==1.6.2
sudo pip2 install colorama==0.3.7
sudo pip2 install argcomplete==1.9.3
sudo pip2 install graphviz==0.8.3
# for some of our workload plotting scripts
sudo pip2 install --upgrade --ignore-installed pyparsing
sudo pip2 install matplotlib==2.2.2
sudo pip2 install pandas==0.22.0
# new awscli on 1.6.0 AMI is broken with our versions of boto3
sudo pip2 install awscli==1.15.76

sudo activate-global-python-argcomplete

# get a regular prompt
echo "PS1='\u@\H:\w\\$ '" >> /home/centos/.bashrc
echo "machine launch script completed" >> /home/centos/machine-launchstatus
```
* Step 4: Add Storage -> Remove the EBS volume. Increase the size of your default root volume to some reasonable amount. 100GB is a good starting point. This instance will be downloading many repos and building full linux images.
* Step 5: Add Tags -> Add them if you'd like
* Step 6: Security Group -> Be sure to select the `FIRESIM_PREFIX-firesim` security group after clicking `Select an existing security group`.
* Review and Launch

Once the instance is running, login using SSH and your key.

```
ssh -i ${YOUR_FIRESIM_PREFIX}-firesim.pem centos@<PUBLIC IP ADDR>
```

The initial connection will take some time as the instance is running our setup script at startup.
Once you are logged in, run:
```
tail -f ~/machine-launchstatus
```
and wait for the `machine launch script completed!` message before continuing. Ctrl-C to exit the tail command once it is finished.

Copy your private key to the instance at `~/${YOUR_FIRESIM_PREFIX}-firesim.pem`. This is required so FireSim can communicate with other instances it spins up.
```
scp -i ${YOUR_FIRESIM_PREFIX}-firesim.pem ${YOUR_FIRESIM_PREFIX}-firesim.pem centos@<PUBLIC IP ADDR>:
```

Clone the FireSim repo and start the setup process. Be sure to set your `FIRESIM_PREFIX` and that it matches the one used earlier.
This variable will be stored in your FireSim configuration after the build process, so you should not have to set this again.
```
export FIRESIM_PREFIX="YOUR_FIRESIM_PREFIX"
cd ~
git clone https://github.com/DARPA-SSITH-Demonstrators/firesim.git
cd firesim
./build-setup.sh fast
```
You may have to enter your username and password for both github and gitlab-ext during this process. If you get it wrong and the
process exits, just run `./build-setup.sh fast` again and it will continue from where it left off.

The build process will take around 1-2 hours on this `t3.xlarge` instance.

Source this file when the build process has finished.
This step must be done every time you SSH into the FireSim Manager instance.
```
cd ~/firesim
source sourceme-f1-manager.sh
```

Finally, initialize your manager instance. Note this script also requires the region to be set:
```
... Copy/Paste your current AWS Credentials into the prompt before continuing ...
... AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN ...
export AWS_DEFAULT_REGION="us-west-2"
firesim managerinit
```

## Run Linux On Existing AFI

If starting fresh, SSH into your manager instance, source the `sourceme-f1-manager.sh` file, and copy/paste your current credentials. Otherwise continue in the same SSH connection.

We need to slightly modify the included Berkeley Boot Loader (`bbl`) to reflect the expected memory map of our GFE processors. Run the following commands to make this change
and start the build process:
```
cd ~/firesim/sw/firesim-software
./init-submodules.sh

cd ~/firesim
./gfe_fixes.sh

cd ~/firesim/sw/firesim-software
./marshal -v build br-base.json
```
This will take some time on this instance with only 4 vCPUs.

Once it finishes, check that you have the files:
* `~/firesim/sw/firesim-software/images/br-base-bin` - the bootloader and kernel image. This gets loaded directly into memory
* `~/firesim/sw/firesim-software/images/br-base.img` - filesystem disk image, accessed via the block device

Launch the F1 instance and start the simulation:
```
cd ~/firesim/deploy
firesim launchrunfarm
firesim infrasetup
firesim runworkload
```

Pay attention to the output of each command to see what they do individually. The final command should display a screen similar to:
```
FireSim Simulation Status @ 2018-05-19 00:38:56.062737
--------------------------------------------------------------------------------
This workload's output is located in:
/home/centos/firesim/deploy/results-workload/2018-05-19--00-38-52-linux-uniform/
This run's log is located in:
/home/centos/firesim/deploy/logs/2018-05-19--00-38-52-runworkload-JS5IGTV166X169DZ.log
This status will update every 10s.
--------------------------------------------------------------------------------
Instances
--------------------------------------------------------------------------------
Instance IP:   172.30.2.174 | Terminated: False
--------------------------------------------------------------------------------
Simulated Switches
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
Simulated Nodes/Jobs
--------------------------------------------------------------------------------
Instance IP:   172.30.2.174 | Job: linux-uniform0 | Sim running: True
--------------------------------------------------------------------------------
Summary
--------------------------------------------------------------------------------
1/1 instances are still running.
1/1 simulations are still running.
--------------------------------------------------------------------------------
```

Take note of the `Instance IP` (`172.30.2.174` in the example above). Open a new SSH connection to your manager instance, source the FireSim `sourceme-f1-manager.sh` file and then run:
```
ssh <INSTANCE IP ADDR>
```

You are now logged into the F1 instance by way of your manager instance. This is the machine actually connected to the FPGA and running the simulation.

FireSim automatically starts a console connection to the running FPGA. Open it:
```
screen -r fsim0
```

You should now see Linux booting up:
```
Commencing simulation.
[    0.000000] OF: fdt: Ignoring memory range 0x80000000 - 0xc0200000
[    0.000000] Forcing kernel command line to: console=hvc0 earlycon=sbi
[    0.000000] Linux version 5.3.0-00002-g6a95b016aba5 (centos@ip-192-168-1-229.us-west-2.compute.internal) (gcc version 9.2.0 (GCC)) #1 SMP Wed May 13 07:57:25 UTC 2020
[    0.000000] earlycon: sbi0 at I/O port 0x0 (options '')
[    0.000000] printk: bootconsole [sbi0] enabled
[    0.000000] initrd not found or empty - disabling initrd
[    0.000000] Zone ranges:
[    0.000000]   DMA32    [mem 0x00000000c0200000-0x00000000ffffffff]
[    0.000000]   Normal   empty
[    0.000000] Movable zone start for each node
[    0.000000] Early memory node ranges
[    0.000000]   node   0: [mem 0x00000000c0200000-0x00000000ffffffff]
[    0.000000] Initmem setup node 0 [mem 0x00000000c0200000-0x00000000ffffffff]
[    0.000000] software IO TLB: mapped [mem 0xfb1fc000-0xff1fc000] (64MB)
[    0.000000] elf_hwcap is 0x112d
[    0.000000] percpu: Embedded 18 pages/cpu s36312 r8192 d29224 u73728
[    0.000000] Built 1 zonelists, mobility grouping on.  Total pages: 258055
...
Mounting /dev/iceblk as root device
[   10.658566] EXT4-fs (iceblk): mounted filesystem without journal. Opts: (null)
Loaded platform drivers, booting from disk:
[   12.500367] random: fast init done
[   12.978251] EXT4-fs (iceblk): re-mounted. Opts: (null)
Starting syslogd: OK
Starting klogd: OK
Running sysctl: OK
Starting mdev: OK
Initializing random number generator... [   26.690846] random: dd: uninitialized urandom read (512 bytes read)
done.
Starting network: OK
[   43.698791] random: httpd: uninitialized urandom read (8 bytes read)
[   43.714622] random: httpd: uninitialized urandom read (8 bytes read)
[   43.733618] random: httpd: uninitialized urandom read (8 bytes read)
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 127.0.1.1. Set the 'ServerName' directive globally to suppress this message
Starting dropbear sshd: OK
launching firesim workload run/command
firesim workload run/command done

Welcome to Buildroot
buildroot login: root
Password:
# 
```

The login is **root** and the password is **firesim**.

End the simulation by typing `poweroff -f` at the Linux prompt (on the target OS, not your instances). Then terminate the run farm as explained below.

**Important**

It is very easy to leave a FireSim F1 instance running and forget about it. These are limited resources and expensive. Back on your manager instance, be sure to run:
```
firesim terminaterunfarm
```
After you are done and answer 'yes' at the prompt. This will terminate your F1 instances.

## Build Your Own Image
A few build recipes have been preset for you. Feel free to change these as needed.

First, define your build recipe in `~/firesim/deploy/config_build_recipes.ini`:
```
...
[firesim-bluespec_p2-dropincore-nic-l2-llc4mb-ddr3]
DESIGN=FireSim
TARGET_CONFIG=WithNIC_DDR3FRFCFSLLC4MB_WithBluespecP2_FireSimSSITHDropInConfig
PLATFORM_CONFIG=F50MHz_BaseF1Config
instancetype=z1d.2xlarge
deploytriplet=None
```

Options generic to either Chisel or Bluespec cores:
* `DESIGN=FireSim` sets the top-level scala class. It is very unlikely you'd want to change this
* `TARGET_CONFIG` is passed to chipyard to build the actual SoC complex. Options can be combined.
  * `WithNIC` adds the IceNIC at `0x62100000`
  * `DDR3FRFCFSLLC4M` adds the standard DDR controller and L2 cache
  * There are two main build strategies available, as explained below. `FireSimSSITHDropInConfig` and `FireSimCloudGFEChiselPXConfig`
* `PATFORM_CONFIG` is used by FireSim to implement platform level options, such as the synthesis target frequency and underlying hardware (only F1 supported). Use `FXXMHz` to select the SoC's frequency. Good options are `F50MHz`, `F75MHz`, and `F90MHz`. Others may work as well.
* `instancetype` sets the EC2 instance used to build the image. The default of `z1d.2xlarge` is a good balance between cost and speed. You'll need an instance with minimum 32GB of RAM.
* `deploytriplet` is currently unused

UART and block devices are always included.

### Build with a "DropIn" SSITH Core - `FireSimSSITHDropInConfig`

This flow enables "dropping in" any processor core that conforms to the expected GFE subsystem. It currently works for BSV-based processors, but would also work for
chisel processors compiled to verilog with some modifications. Information on adding new drop-in cores can be found in the chipyard repo README (to come).

For FireSim, you can select the drop-in replacement using an optional modifier in the `TARGET_CONFIG` recipe.

Available drop-ins:
* `WithBluespecP2` - specifies to use the BSV P2 (Flute) repo as the blackbox core (default).

### Build with a CloudGFE P1 Core (Chisel based) - `FireSimCloudGFEChiselP1Config`

This flow compiles a P1 (32-bit) processor directly from Chisel source. Append this configuration option to the end of the `TARGET_CONFIG` string, ex: `WithNIC_DDR3FRFCFSLLC4MB_FireSimCloudGFEChiselP1Config`.

### Build with a CloudGFE P2 Core (Chisel based) - `FireSimCloudGFEChiselP2Config`

This flow compiles a P2 (64-bit) processor directly from Chisel source. Append this configuration option to the end of the `TARGET_CONFIG` string, ex: `WithNIC_DDR3FRFCFSLLC4MB_FireSimCloudGFEChiselP2Config`.

### Continuing the build

Now define your build tag in `~/firesim/deploy/config_build.ini`:
```
[builds]
# this section references builds defined in config_build_recipes.ini
# if you add a build here, it will be built when you run buildafi
#firesim-cloudgfe-chisel-p2-nic-l2-llc4mb-ddr3
#firesim-cloudgfe-chisel-p1-nic-l2-llc4mb-ddr3
firesim-bluespec_p2-dropincore-nic-l2-llc4mb-ddr3
```

You can specify multiple builds, but your AWS account may not have sufficient vCPU limits to support concurrent builds. You can also add your build tag to the `agfitoshare` section, which will
automatically share the final AFIs with any accounts listed in the `sharewithaccounts` section.

Now launch the build. It's strongly encouraged to use `screen` or `mosh` to launch the build process. If your SSH connection dies during the build, which could take 5-6 hours, the build process may not finish.
```
screen
firesim buildafi
```

FireSim will first build the verilog netlist with your chosen build recipe using chipyard. It will then package up the netlist with other AWS components and send them
to a build instance where Vivado is actually executed.

At the end of the build process, the manager instance will submit your Vivado checkpoint to AWS for final encryption and packaging. 
You'll see a continuous stream of `Pending...` messages while this is happening. It can take up to an hour.

If your SSH connection and AWS credentials remained active, you'll receive an e-mail when the build is finished with the configuration blurb to add to `~/firesim/deploy/config_hwdb.ini`.
It will also be printed in the terminal window and saved to a file in `~/firesim/deploy/built-hwdb-entries`.

Finally add the new image to `~/firesim/deploy/config_hwdb.ini`. Example:
```
[firesim-bluespec_p2-dropincore-nic-l2-llc4mb-ddr3e
agfi=agfi-0e9a472782e8e53c2
deploytripletoverride=None
customruntimeconfig=None
```

And update `~/firesim/deploy/config_runtime.ini` to point to the new tag:
```
# This references a section from config_hwconfigs.ini
# In homogeneous configurations, use this to set the hardware config deployed
# for all simulators
# defaulthwconfig=firesim-cloudgfe-chisel-p2-nic-l2-llc4mb-ddr3
defaulthwconfig=firesim-bluespec_p2-dropincore-nic-l2-llc4mb-ddr3
```

Note: You can build new AFIs under existing tags and just update the `agfi=<AGFI Number>` option in `config_hwdb.ini` when it is finished building.

Now you can follow the instructions above for running Linux on your new build.

## Notes and Future Additions
* You can transfer binaries to the F1 instance and run the simulation manually from there. Roughly:
```
sudo fpga-clear-local-image -S 0
sudo fpga-load-local-image -S 0 -I AFI_ID
cd ~/sim_slot_0
./VFireSim ~/path/to/elf/file ... options to come ...
```
This will dump the UART output to the console. You can Ctrl-C to stop the simulation (does not clear the FPGA slot).

* Networking does not work out of the box. Need to make some modifications to the switch software and run iptables setup on the F1 instance manually. Will document
so we can decide if this should be automated in FireSim or just used in our own solution

