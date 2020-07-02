# CloudGFE FireSim - On Prem

## Contents

1. [What is FireSim On Prem?](#what-is-firesim-on-prem)
2. [Getting Started](#getting-started)
    1. [Quick Setup](#quick-setup)
    2. [FireSim Docker Containers](#firesim-docker-containers)
    3. [One-Time Setup](#one-time-setup)
    4. [Setup Manager](#setup-manager)
4. [Build an AFI](#build-an-afi)
    1. [Build with a Drop-In Core](#build-with-a-dropin-ssith-core---firesimssithdropinconfig)
    2. [Build with a Chisel P1](#build-with-a-cloudgfe-p1-core-chisel-based---firesimcloudgfechiselp1config)
    3. [Build with a Chisel P2](#build-with-a-cloudgfe-p2-core-chisel-based---firesimcloudgfechiselp2config)
    4. [Continuing the Build](#continuing-the-build)
    5. [Update HWDB](#update-hwdb)
    6. [Build Software Support Package](#build-software-support-package)
5. [Automation Summary](#automation-summary)
6. [Additional Devices](#additional-devices)
    1. [RNG](#rng)
    2. [DMIBridge](#dmibridge)
    
## What is FireSim On Prem?

FireSim is an [open-source](https://github.com/firesim/firesim) cycle-accurate
FPGA-accelerated full-system hardware simulation platform that runs on cloud FPGAs (Amazon EC2 F1).

This is a modified version of FireSim to facilitate on premises builds of AFIs.
FireSim On Prem has been modified primarily to build AFIs and associated software packages - some existing FireSim functions tied tightly to AWS have been disabled (ex: run farms).

In CloudGFE, FireSim is capable of running both Bluespec and Chisel based SSITH cores. There are two approaches for integrating your custom core, as described later.

The FireSim documentation is very good for learning the basics.
If you'd like to learn more about FireSim, see here: https://docs.fires.im/. 
Another good overview (in video format) is our tutorial from the Chisel Community Conference on [YouTube](https://www.youtube.com/watch?v=S3OriQnJXYQ).

## Getting Started

This simple tutorial will guide you through setting up an On Prem FireSim build system.
It will assume you already have access to the AWS DARPA portal and have access to either the FireSim Docker containers or can create your own build environment.

### Quick Setup

There are now quick-setup packages available that use pre-built Linux/FreeBSD images along with prebuilt AFIs. For details, [see this README](https://github.com/DARPA-SSITH-Demonstrators/BESSPIN-CloudGFE/blob/master/FireSim/minimal_cloudgfe.md)

### FireSim Docker Containers

Two docker containers have been created to make running FireSim on premises easier.

The first, `artifactory.galois.com:5008/firesim:runtime`, contains all the necessary packages for running FireSim scripts, building netlists from Chisel, and compiling support software (host-side communication binaries, kernel modules, etc).

The second, `artifactory.galois.com:5008/firesim:bitstream_gen`, contains the correct version of Vivado and the AWS F1 license to build the Vivado design files for AWS to convert into AFIs.

It is possible to run this version of FireSim without either of these docker containers, but that process is not documented here. See [the docker build scripts](https://gitlab-ext.galois.com/ssith/docker-tools) for an example of the environment you'll need to create.

**Note** It is assumed the environment you are running FireSim in matches that of the F1 instances you'll eventually use. For example, if you run this on Debian Buster, you'll need to set the F1 instance's AMI to match. The `runtime` docker container has been carefully matched to the `FPGA Developer 1.6.0` AMI.

### One-Time Setup

There is a one-time setup required to initialize your FireSim system.

If you plan on interacting with AWS directly (to create AFIs, share them, etc), set your AWS credentials using environmental variables. If you plan to disable AWS, this step can be skipped. The values can be easily copy/pasted from the [DARPA portal](https://darpa-ssith.awsapps.com/start#/):
```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
export AWS_DEFAULT_REGION='us-west-2'
```
Be sure to add your default region, which is not included on the DARPA page.

It's also strongly advised to use SSH key forwarding or `ssh-agent` to manage access to both github.com and gitlab-ext.galois.com. Repos are spread across these two sites. The docker start script will automatically pass-through an SSH agent configuration.

If using docker, start the environment using the `./start_docker.sh` script. If you don't already have the docker image downloaded, it will take some time to run this the first time. Subsequent runs will be quick.
```
$ cd firesim
$ ./start_docker.sh 
[root@ba58e3742eae firesim]# 
```

Now source the local build setup script. This only has to be done once:
```
[root@ba58e3742eae firesim]# source build-setup-local.sh
```

Finally, run either the firesim `managerinit` or `managerinit_noaws` task to complete the initial setup. 
The regular (not `_noaws`) task requests an email address
to receive notifications when an AFI has been completed. If automating this setup, you can `echo` the address (or 
an empty string) into the command. If you cannot connect to AWS, use `managerinit_noaws` to disable all AWS communication steps:
```
[root@ba58e3742eae firesim]# firesim managerinit
or
[root@ba58e3742eae firesim]# echo "user@address.com" | firesim managerinit
or
[root@ba58e3742eae firesim]# echo "" | firesim managerinit
or
[root@ba58e3742eae firesim]# firesim managerinit_noaws
```

### No AWS Flow

At this point, you should also modify `firesim/deploy/config_build.ini` to disable AWS connections if necessary.
Modify the `enableaws` option in the `[afibuild]` section as shown:
```
[afibuild]

s3bucketname=firesim-localuser
buildinstancemarket=ondemand
spotinterruptionbehavior=terminate
spotmaxprice=ondemand
postbuildhook=
enableaws=false
```

## Build an AFI
Build recipes for the three supported CPUs have been provided for you. Feel free to change these as needed.

First, define your build recipe in `firesim/deploy/config_build_recipes.ini`:
```
...
[firesim-cloudgfe-chisel-p2]
DESIGN=FireSim
TARGET_CONFIG=WithNIC_DDR3FRFCFSLLC4MB_FireSimCloudGFEChiselP2Config
PLATFORM_CONFIG=F100MHz_BaseF1Config
instancetype=z1d.2xlarge
deploytriplet=None
```

Options generic to either Chisel or Bluespec cores:
* `DESIGN=FireSim` sets the top-level scala class. It is very unlikely you'd want to change this
* `TARGET_CONFIG` is passed to chipyard to build the actual SoC complex. Options can be combined.
  * `WithNIC` adds the IceNet NIC
  * `DDR3FRFCFSLLC4M` adds the standard DDR controller and L2 cache
  * There are two main build strategies available, as explained below. `FireSimSSITHDropInConfig` and `FireSimCloudGFEChiselPXConfig`
* `PATFORM_CONFIG` is used by FireSim to implement platform level options, such as the synthesis target frequency and underlying hardware (only F1 supported). Use `FXXMHz` to select the SoC's frequency. Good options are `F50MHz` and `F100MHz`. Others may work as well.
* `instancetype` will be ignored by on-premise FireSim but is required to be set for compatibility
* `deploytriplet` is currently unused

**Note** The Bluespec P2 currently does not build cleanly at 100MHz. This core has been preconfigured to synthesize at 90MHz.

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
#firesim-cloudgfe-chisel-p2
#firesim-cloudgfe-chisel-p1
firesim-cloudgfe-bluespec-p2
```

It is possible to specify multiple builds, but full functionality for this approach is not yet implemented. FireSim will only build the first AFI in the list. It will generate software packages (described later) for all listed builds.
You can also add your build tag to the `agfitoshare` section, which will
automatically share the final AFIs with any accounts listed in the `sharewithaccounts` section.

Now launch the build. It takes about 5-6 hours:
```
[root@ba58e3742eae firesim]# firesim buildafi
```

At the end of the build process, assuming your AWS credentials are still valid, FireSim will submit your Vivado checkpoint to AWS for final encryption and packaging. 
You'll see a continuous stream of `Pending...` messages while this is happening. It can take up to an hour.
If you provided an email address during the `managerinit` task, you'll also receive an e-mail when the build is finished with the configuration blurb to add to `firesim/deploy/config_hwdb.ini`.
It will also be printed in the terminal window and saved to a file in `firesim/deploy/built-hwdb-entries`.

If you opted for disabling AWS, firesim will output information about continuing the build process on a AWS-connected computer.
Copy the checkpoint file to S3 as described and run the provided `aws ec2` command to start the AFI generation process. Generating
an AFI from a checkpoint takes up to an hour. You can add the AGFI provided by the `aws ec2` command to `firesim/deploy/config_hwdb.ini`
to continue building the software but must wait for the process to finish before using the AFI.


### Update HWDB

FireSim uses a `hwdb` file to track generated AFIs. This file is not updated automatically by FireSim.
After building an AFI, you will need to add your newly created image to the database either manually or using:
```
[root@ba58e3742eae firesim]# cat deploy/built-hwdb-entries/firesim-cloudgfe-* > deploy/config_hwdb.ini
```

This must be done before building the software support package to ensure the correct AGFI identifier is used.

### Build Software Support Package

A new task has been aded to FireSim On Prem that generates software packages for the F1 host instance:

```
[root@ba58e3742eae firesim]# firesim buildlocalsw
```

The output software package include:
```
sw
├── kmods
│   ├── nbd.ko
│   └── xdma.ko
├── setup.sh
├── sim
│   ├── FireSim.asserts
│   ├── FireSim-f1
│   ├── kill_sim.sh
│   ├── libdwarf.so.1
│   ├── libelf.so.1
│   ├── run_sim.sh
│   ├── runtime.conf
│   └── switch0
└── support
    └── switchconfig.h
```

`setup.sh` will configure the F1 instance and load the necessary kernel modules.

`sim/run_sim.sh` is a sample run script that sets up networking and executes the `FireSim-f1` simulator with the proper arguments, including a block device image and provided ELF.

The FireSim `buildlocalsw` task will populate this folder for you, currently preforming the following tasks:
* Copy initial skeleton from `firesim/platforms/f1/run-skel`
* Build `FireSim-f1` executable based on actual SoC configuration
* Build `xdma.ko` kernel module from source
  * Currently this primarily supports the exact kernel version of the `FPGA Developer 1.6.0` AMI. But others may work
* Copies the current version of `libdwarf` and `libelf` from the RISC-V Toolchain
* Builds the switch software, `switch0`, which generates the `tap0` device to communicate between host and FPGA ethernet
* Populates the run script with the correct AGFI and configuration names
* Generates a tgz package
* Uploads the tgz package to AWS S3

The software package uploads to `s3://firesim-localuser/swpkgs/firesim-cloudgfe-processor-PX-sw.tgz` by default. If you've
disabled AWS, firesim will print out the path to the tgz file for you to manually copy.

**Important** The build flow requires a consistent environment between where `firesim buildlocalsw` is run and the F1 instance.
This means the general OS version, installed packages, and even kernel version should match as closely (or exactly) as possible.

## Automation Summary

To automate building AFIs and distributing software, your flow should:
* Set the proper SSH keys, key forwarding, etc to ensure access to both github.com and gitlab-ext.galois.com
* Checkout the firesim repo and use a FireSim On Prem enabled branch (such as this one)
* Populate fresh AWS credentials using environmental variables that will remain active for at least 5 hours, including `AWS_DEFAULT_REGION`
* (Recommended) Start Docker by running `./start_docker.sh`
* Run `source ./build-setup-local.sh`
  * If you don't source this script, you either need to restart docker or run `source sourceme-f1-manager.sh`
* Run `echo "" | firesim managerinit`
  * Or populate an email address that will receive notifications
* Modify `deploy/config_build.ini` and `deploy/config_build_recipes.ini` if necessary.
  * You'll want to at least set the default build target if that is not set by the branch
* Build the AFI using `firesim buildlocalafi`
* Update the hwdb using `cd deploy; cat built-hwdb-entries/firesim-cloudgfe-* > config_hwdb.ini`
* Build and deploy the corresponding software package: `firesim buildlocalsw`

At the end of this process, you'll have an AFGI identifier and a software package stored on S3 to go with it.

**Notes**
* The `nbd.ko` module is not currently re-compiled from source. It's unclear if this module is actually required, so that has been left as a 'to-do'. The provided kernel module is compatible with CentOS 7.6 (FPGA Developer AMI)

## Additional Devices

New bridges have been introduced for use in the SSITH program.

### RNG

The RandomBridge interfaces with a new `SSITHRNG` device connected to the SoC at address `0x63000000`. This device was designed to be software compatible with the STMicroelectronics HW RNG; specifically the [st-rng.c](https://github.com/torvalds/linux/blob/master/drivers/char/hw_random/st-rng.c) Linux driver. However, this simple interface can be used with any OS or bare metal program.

The device contains a 4-entry deep FIFO that is constantly filled with 32-bit random values. In FireSim, these values are sourced from the host OS's `/dev/random` device, so their quality will match that of the host machine. FireSim first transfers the values into a different 128-entry queue, which then feeds `SSITHRNG`. Once the 128-entry queue empties to a software programmable threshold value (defaults to 16), FireSim will refill the remaining queue space in a burst operation. This effectively keeps the internal RNG device consistently fed.

There are two registers defined:
```
(offset from 0x63000000)
0x20 -> Status Register (8-bits)
0x24 -> Random Data Register (32-bits)
```

#### Status Register

_0x63000020_

There are only 2 bits of the status register currently used. Bit 5 is `FIFO_FULL`, indicating the SSITHRNG has 4 random values available. Bit 6 is `FIFO_NOTEMPTY`, indicating there is at least one random value available. 

#### Data Register

_0x63000024_

The data register returns a single 32-bit random word. On every read operation, the current value is drained from the FIFO automatically allowing a new value to be added.

#### Operation

##### Bare Metal / Non-Debian OS
It should be safe to simply read directly from the Data Register repeatedly. By the time the RISC-V CPU's first read operation could reach the SSITHRNG, the FIFO will already be completely full. And it is very unlikely the device will run out of random values due to how host-to-target communication in FireSim works.

However, a fully safe approach would be to first poll the Status register to check if either bits 5 or 6 are set. Check bit 6 if you only need a single value for some period of time. Use bit 5 if you need multiple data words. It allows you to write a slightly more performant loop that can safely request 4 random words before polling the status register again.

##### Linux
Our Debian Linux builds will now include the driver for the HW RNG and `rng-tools`, which will seed the Linux random API with random values from `/dev/hwrng`. Your programs can either use the standard `/dev/random` or `/dev/urandom` interfaces, or they can access the HW RNG directly with `/dev/hwrng`.

### DMIBridge

This bridge exposes the DMI interface to the host. It enables sending requests and receiving responses from the debug module. This has been combined with existing code that implements a JTAG state machine in C, bridging OpenOCD's `jtagvpi` interface to the exposed DMI interface. Putting everything together, it is now possible to connect `gdb` directly to the core running inside FireSim.

This functionality is enabled by adding the `+debug_enable` argument to `FireSim-f1`. You can also optionally specify a port number for the `jtagvpi` socket to OpenOCD using `+debug_port=NUMBER`. The port number defaults to `5555`.

A sample `openocd.cfg` and `init.gdb` have been included with the proper configuration options in `platforms/f1/run-skel/sim/`. `run_gdb.sh` in the same folder wraps all the commands into a simple script.

#### Under The Hood

The `gdb <-> openocd <-> jtagvpi <-> dmi <-> DebugModule` connection is currently capped at 30KB/sec, therefore some additional changes were made to help with loading large binaries. The host-side `dmi_t` C++ bridge software will set a `dbg_connected` bit inside the target's `DMIBridge` device when you enable debugging using `+debug_enable`. This bit is further populated to the `MMInt` device, which is used to mimic the `CLINT` in our FireSim SoC. This flag is exposed to the CPU in an additional read-only register. This all happens before the core is released from reset. `bootrom.cloudgfe.S` has been updated to immediately check if the debugger is connected, and if so, set `$a0` and `$a1` with the appropriate values before jumping to a `wfi` loop. It will not initialize the PLIC, interrupts, or set any additional options as it normally would.

Then, FireSim is allowed to populate the memory with the given ELF. `MMInt` intercepts the "start" message that would normally kickoff booting from main memory and instead raises a flag that the `dmi_t` bridge software polls to determine when ELF loading has finished. Only at this point does it actually allow OpenOCD to connect to the debug module.

In short, this means by the time `gdb` connects to the core, the memory has already been populated and the `$a0` and `$a1` registers have been properly set for the `bbl` bootloader to run. `gdb` can set the PC to `0xC0000000` and start debugging the chosen program.

#### Using GDB

First enable debug support in `run_sim.sh`. Set `DEBUG_ENABLE=1` near the top of the script. When you run `./run_sim.sh`, it will pause early waiting for the debugger to connect. Use your favorite multi-terminal approach (creating a new screen tab, disconnecting from screen, or starting a new SSH connection) to run `./run_gdb.sh <elf_file>` with the same ELF. The RISCV toolchain will be automatically downloaded if necessary and gdb will start. Once connected, the FireSim simulation will continue. `gdb` starts in the halted state with the memory pre-populated with your ELF file (no need to run `load`).
