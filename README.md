# CloudGFE FireSim - On Prem

## Contents

1. [What is FireSim On Prem?](#what-is-firesim-on-prem)
2. [Getting Started](#getting-started)
    1. [Quick Setup](#quick-setup)
    2. [FireSim Docker Containers](#firesim-docker-containers)
    3. [One-Time Setup](#one-time-setup)
    4. [Setup Manager](#setup-manager)
3. [Run Linux on Existing AFI](#run-linux-on-existing-afi)
4. [Build Your Own Image](#build-your-own-image)
5. [Notes and Future Additions](#notes-and-future-additions)

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

The first, `artifactory.galois.com:5008/firesim:sw_gen`, contains all the necessary packages for running FireSim scripts, building netlists from Chisel, and compiling support software (host-side communication binaries, kernel modules, etc).

The second, `artifactory.galois.com:5008/firesim:bitstream_gen`, contains the correct version of Vivado and the AWS F1 license to build the Vivado design files for AWS to convert into AFIs.

It is possible to run this version of FireSim without either of these docker containers, but that process is not documented here. See [the docker build scripts](https://gitlab-ext.galois.com/ssith/docker-tools) for an example of the environment you'll need to create.

**Note** It is assumed the environment you are running FireSim in matches that of the F1 instances you'll eventually use. For example, if you run this on Debian Buster, you'll need to set the F1 instance's AMI to match. The `sw_gen` docker container has been carefully matched to the `FPGA Developer 1.6.0` AMI.

### One-Time Setup

There is a one-time setup required to initialize your FireSim system.

First, set your AWS credentials using environmental variables. These can be easily copy/pasted from the [DARPA portal](https://darpa-ssith.awsapps.com/start#/):
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

Finally, run the firesim `managerinit` task to complete the initial setup. This process requests an email address
to receive notifications when an AFI has been completed. If automating this setup, you can `echo` the address (or 
an empty string) into the command:
```
[root@ba58e3742eae firesim]# firesim managerinit
or
[root@ba58e3742eae firesim]# echo "user@address.com" | firesim managerinit
or
[root@ba58e3742eae firesim]# echo "" | firesim managerinit
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

If you provided an email address during the `managerinit` task, you'll also receive an e-mail when the build is finished with the configuration blurb to add to `~/firesim/deploy/config_hwdb.ini`.
It will also be printed in the terminal window and saved to a file in `~/firesim/deploy/built-hwdb-entries`.

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

The software package uploads to `s3://firesim-localuser/swpkgs/firesim-cloudgfe-processor-PX-sw.tgz` by default.

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
