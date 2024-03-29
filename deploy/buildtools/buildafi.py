from __future__ import with_statement
import json
import time
import random
import string
import logging
import subprocess

from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib.project import rsync_project
from awstools.afitools import *
from awstools.awstools import send_firesim_notification
from util.streamlogger import StreamLogger, InfoStreamLogger

import os.path

rootLogger = logging.getLogger()

def get_local_shell():
    return '/bin/bash'

def get_deploy_dir():
    """ Must use local here. determine where the firesim/deploy dir is """
    with StreamLogger('stdout'), StreamLogger('stderr'):
        deploydir = local("pwd", capture=True)
    return deploydir

def replace_rtl(conf, buildconfig):
    """ Run chisel/firrtl/fame-1, produce verilog for fpga build.

    THIS ALWAYS RUNS LOCALLY"""
    builddir = buildconfig.get_build_dir_name()
    fpgabuilddir = "hdk/cl/developer_designs/cl_" + buildconfig.get_chisel_triplet()
    ddir = get_deploy_dir()

    rootLogger.info("Running replace-rtl to generate verilog for " + str(buildconfig.get_chisel_triplet()))

    with prefix('cd ' + ddir + '/../'), prefix('source sourceme-f1-manager.sh'), prefix('export CL_DIR={}/../platforms/f1/aws-fpga/{}'.format(ddir, fpgabuilddir)), prefix('cd sim/'), StreamLogger('stdout'), StreamLogger('stderr'):
        local("""pwd""", shell=get_local_shell())
        local(buildconfig.make_recipe("replace-rtl"), shell=get_local_shell())
        local("""mkdir -p {}/results-build/{}/""".format(ddir, builddir), shell=get_local_shell())
        local("""cp $CL_DIR/design/cl_firesim_generated.sv {}/results-build/{}/cl_firesim_generated.sv""".format(ddir, builddir), shell=get_local_shell())

    # build the fpga driver that corresponds with this version of the RTL
    with prefix('cd ' + ddir + '/../'), prefix('source sourceme-f1-manager.sh'), prefix('cd sim/'), StreamLogger('stdout'), StreamLogger('stderr'):
        local(buildconfig.make_recipe("f1"), shell=get_local_shell())

@parallel
def aws_build(global_build_config, bypass=False):
    """ Run Vivado, convert tar -> AGFI/AFI. Then terminate the instance at the end.
    conf = buildconfig dicitonary
    bypass: since this function takes a long time, bypass just returns for
    testing purposes when set to True. """
    if bypass:
        ### This is duplicated from the end of the function.
        buildconfig = global_build_config.get_build_by_ip(env.host_string)
        buildconfig.terminate_build_instance(buildconfig)
        return

    rootLogger.info("Running process to build AGFI from verilog.")

    # First, Produce dcp/tar for design. Runs on remote machines, out of
    # /home/centos/firesim-build/ """
    ddir = get_deploy_dir()
    buildconfig = global_build_config.get_build_by_ip(env.host_string)
    builddir = buildconfig.get_build_dir_name()
    # local AWS build directory; might have config-specific changes to fpga flow
    fpgabuilddir = "hdk/cl/developer_designs/cl_" + buildconfig.get_chisel_triplet()
    remotefpgabuilddir = "hdk/cl/developer_designs/cl_firesim"

    # first, copy aws-fpga to the build instance. it will live in
    # firesim-build/platforms/f1/
    with StreamLogger('stdout'), StreamLogger('stderr'):
        run('mkdir -p /home/centos/firesim-build/platforms/f1/')
    # do the rsync, but ignore any checkpoints that might exist on this machine
    # (in case builds were run locally)
    # extra_opts -l preserves symlinks
    with StreamLogger('stdout'), StreamLogger('stderr'):
        rsync_cap = rsync_project(local_dir=ddir + "/../platforms/f1/aws-fpga",
                      remote_dir='/home/centos/firesim-build/platforms/f1/',
                      ssh_opts="-o StrictHostKeyChecking=no",
                      exclude="hdk/cl/developer_designs/cl_*",
                      extra_opts="-l", capture=True)
        rootLogger.debug(rsync_cap)
        rootLogger.debug(rsync_cap.stderr)
        rsync_cap = rsync_project(local_dir=ddir + "/../platforms/f1/aws-fpga/{}/*".format(fpgabuilddir),
                      remote_dir='/home/centos/firesim-build/platforms/f1/aws-fpga/' + remotefpgabuilddir,
                      exclude='build/checkpoints',
                      ssh_opts="-o StrictHostKeyChecking=no",
                      extra_opts="-l", capture=True)
        rootLogger.debug(rsync_cap)
        rootLogger.debug(rsync_cap.stderr)

    # run the Vivado build
    with prefix('cd /home/centos/firesim-build/platforms/f1/aws-fpga'), \
         prefix('source hdk_setup.sh'), \
         prefix('export CL_DIR=/home/centos/firesim-build/platforms/f1/aws-fpga/' + remotefpgabuilddir), \
         prefix('cd $CL_DIR/build/scripts/'), InfoStreamLogger('stdout'), InfoStreamLogger('stderr'):
        run('./aws_build_dcp_from_cl.sh -foreground')

    # rsync in the reverse direction to get build results
    with StreamLogger('stdout'), StreamLogger('stderr'):
        rsync_cap = rsync_project(local_dir="""{}/results-build/{}/""".format(ddir, builddir),
                      remote_dir='/home/centos/firesim-build/platforms/f1/aws-fpga/' + remotefpgabuilddir,
                      ssh_opts="-o StrictHostKeyChecking=no", upload=False, extra_opts="-l",
                      capture=True)
        rootLogger.debug(rsync_cap)
        rootLogger.debug(rsync_cap.stderr)

    ## next, do tar -> AGFI
    ## This is done on the local copy

    afi = None
    agfi = None
    s3bucket = global_build_config.s3_bucketname
    afiname = buildconfig.name

    # construct the "tags" we store in the AGFI description
    tag_buildtriplet = buildconfig.get_chisel_triplet()
    tag_deploytriplet = tag_buildtriplet
    if buildconfig.deploytriplet != "None":
        tag_deploytriplet = buildconfig.deploytriplet

    # the asserts are left over from when we tried to do this with tags
    # - technically I don't know how long these descriptions are allowed to be,
    # but it's at least 256*3, so I'll leave these here for now as sanity
    # checks.
    assert len(tag_buildtriplet) <= 255, "ERR: aws does not support tags longer than 256 chars for buildtriplet"
    assert len(tag_deploytriplet) <= 255, "ERR: aws does not support tags longer than 256 chars for deploytriplet"

    with StreamLogger('stdout'), StreamLogger('stderr'):
        is_dirty_str = local("if [[ $(git status --porcelain) ]]; then echo '-dirty'; fi", capture=True)
        hash = local("git rev-parse HEAD", capture=True)
    tag_fsimcommit = hash + is_dirty_str

    assert len(tag_fsimcommit) <= 255, "ERR: aws does not support tags longer than 256 chars for fsimcommit"

    # construct the serialized description from these tags.
    description = firesim_tags_to_description(tag_buildtriplet, tag_deploytriplet, tag_fsimcommit)

    # if we're unlucky, multiple vivado builds may launch at the same time. so we
    # append the build node IP + a random string to diff them in s3
    global_append = "-" + env.host_string + "-" + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10)) + ".tar"

    with lcd("""{}/results-build/{}/cl_firesim/build/checkpoints/to_aws/""".format(ddir, builddir)), StreamLogger('stdout'), StreamLogger('stderr'):
        files = local('ls *.tar', capture=True)
        rootLogger.debug(files)
        rootLogger.debug(files.stderr)
        tarfile = files.split()[-1]
        s3_tarfile = tarfile + global_append
        localcap = local('aws s3 cp ' + tarfile + ' s3://' + s3bucket + '/dcp/' + s3_tarfile, capture=True)
        rootLogger.debug(localcap)
        rootLogger.debug(localcap.stderr)
        agfi_afi_ids = local("""aws ec2 create-fpga-image --input-storage-location Bucket={},Key={} --logs-storage-location Bucket={},Key={} --name "{}" --description "{}" """.format(s3bucket, "dcp/" + s3_tarfile, s3bucket, "logs/", afiname, description), capture=True)
        rootLogger.debug(agfi_afi_ids)
        rootLogger.debug(agfi_afi_ids.stderr)
        rootLogger.debug("create-fpge-image result: " + str(agfi_afi_ids))
        ids_as_dict = json.loads(agfi_afi_ids)
        agfi = ids_as_dict["FpgaImageGlobalId"]
        afi = ids_as_dict["FpgaImageId"]
        rootLogger.info("Resulting AGFI: " + str(agfi))
        rootLogger.info("Resulting AFI: " + str(afi))

    rootLogger.info("Waiting for create-fpga-image completion.")
    results_build_dir = """{}/results-build/{}/""".format(ddir, builddir)
    with lcd(results_build_dir), StreamLogger('stdout'), StreamLogger('stderr'):
        checkstate = "pending"
        while checkstate == "pending":
            imagestate = local("""aws ec2 describe-fpga-images --fpga-image-id {} | tee AGFI_INFO""".format(afi), capture=True)
            state_as_dict = json.loads(imagestate)
            checkstate = state_as_dict["FpgaImages"][0]["State"]["Code"]
            rootLogger.info("Current state: " + str(checkstate))
            time.sleep(10)

    # copy the image to all regions for the current user
    copy_afi_to_all_regions(afi)

    message_title = "FireSim FPGA Build Completed"
    agfi_entry = "[" + afiname + "]\nagfi=" + agfi + "\ndeploytripletoverride=None\ncustomruntimeconfig=None\n\n"
    message_body = "Your AGFI has been created!\nAdd\n" + agfi_entry + "\nto your config_hwdb.ini to use this hardware configuration."

    send_firesim_notification(message_title, message_body)

    rootLogger.info(message_title)
    rootLogger.info(message_body)

    # for convenience when generating a bunch of images. you can just
    # cat all the files in this directory after your builds finish to get
    # all the entries to copy into config_hwdb.ini
    hwdb_entry_file_location = """{}/built-hwdb-entries/""".format(ddir)
    local("mkdir -p " + hwdb_entry_file_location)
    with open(hwdb_entry_file_location + "/" + afiname, "w") as outputfile:
        outputfile.write(agfi_entry)

    if global_build_config.post_build_hook:
        with StreamLogger('stdout'), StreamLogger('stderr'):
            localcap = local("""{} {}""".format(global_build_config.post_build_hook,
                                                results_build_dir,
                                                capture=True))
            rootLogger.debug("[localhost] " + str(localcap))
            rootLogger.debug("[localhost] " + str(localcap.stderr))

    rootLogger.info("Build complete! AFI ready. See AGFI_INFO.")
    rootLogger.info("Terminating the build instance now.")
    buildconfig.terminate_build_instance()

def local_sw_pkg(conf, buildconfig):
    """ Package F1 instance software required to run current AGFI """
    rootLogger.info("Running process to build local SW package.")

    ddir = get_deploy_dir()
    builddir = buildconfig.name
    triplet = buildconfig.get_chisel_triplet()
    s3bucket = conf.s3_bucketname
    swdir = "{}/results-build/{}/sw".format(ddir, builddir)
    switchbuilddir = "{}/results-build/{}/switch-build".format(ddir, builddir)
    switchswdir = "{}/../target-design/switch/".format(ddir)
    swpkgname = "{}-sw".format(buildconfig.name)
    hwconf = conf.hwdb.get_runtimehwconfig_from_name(buildconfig.name)

    def local_logged(startdir, command):
        """ Run local command with logging. """
        with prefix('cd ' + startdir), StreamLogger('stdout'), StreamLogger('stderr'):
            localcap = local(command, shell=get_local_shell(), capture=True)
            rootLogger.debug(localcap)
            rootLogger.debug(localcap.stderr)

    # Copy the skeleton folder
    local_logged(ddir + '/../', 'rm -rf {} && mkdir -p {}'.format(swdir, swdir))
    local_logged(ddir + '/../', 'cp -R platforms/f1/run-skel/* {}/'.format(swdir))

    # This is likely already done, but run it again just to be safe. build the fpga driver that corresponds with this version of the RTL
    rootLogger.info("Building FireSim-f1 executable")
    with prefix('cd ' + ddir + '/../'), prefix('source sourceme-f1-manager.sh'), prefix('cd sim/'), StreamLogger('stdout'), StreamLogger('stderr'):
        local(buildconfig.make_recipe("f1"), shell=get_local_shell())
    local_logged(ddir + '/../sim', 'cp output/f1/{}/FireSim-f1 {}/sim/FireSim-f1'.format(triplet, swdir))
    local_logged(ddir + '/../sim', 'cp output/f1/{}/runtime.conf {}/sim/runtime.conf'.format(triplet, swdir))

    # Build the xdma driver using our current OS
    rootLogger.info("Building xdma driver - assuming current OS (or docker container) matches that of the F1 instance!!")
    # This should be improved to handle this more generically, but it'll do for now...
    if os.path.exists("/.dockerenv"):
        local_logged(ddir + '/../', 'make -C /usr/src/kernels/3.10.0-957.5.1.el7.x86_64 M=$(pwd)/platforms/f1/aws-fpga/sdk/linux_kernel_drivers/xdma modules')
        local_logged(ddir + '/../', 'cp platforms/f1/aws-fpga/sdk/linux_kernel_drivers/xdma/xdma.ko {}/kmods/'.format(swdir))
    else:
        with prefix('cd ' + ddir + '/../platforms/f1/aws-fpga/sdk/linux_kernel_drivers/xdma'), StreamLogger('stdout'), StreamLogger('stderr'):
            local('make clean ; make')
            local('cp xdma.ko {}/results-build/{}/sw/kmods/'.format(ddir, builddir))

    # Copy our version of libdwarf and libelf
    rootLogger.info("Copying current version of libdwarf and libelf")
    local_logged(ddir + '/../', 'cp $RISCV/lib/libdwarf.so {}/sim/libdwarf.so.1'.format(swdir))
    local_logged(ddir + '/../', 'cp $RISCV/lib/libelf.so {}/sim/libelf.so.1'.format(swdir))

    # Build the switch software
    # This is going to assume we are using the standard 2 port setup no matter what.. This can result in the switch being
    # completely useless and freezing the simulator if you have a different setup
    rootLogger.info("Building the switch software")
    local_logged(ddir + '/../', 'rm -rf {} && cp -R {} {}'.format(switchbuilddir, switchswdir, switchbuilddir))
    local_logged(switchbuilddir, 'cp ../sw/support/switchconfig.h .')
    local_logged(switchbuilddir, 'make && cp switch ../sw/sim/switch0')

    # Update some placeholders
    rootLogger.info("Updating placeholders")
    local_logged(swdir, 'sed -i s/FIRESIM_AGFI/{}/g sim/run_sim.sh'.format(hwconf.agfi))
    local_logged(swdir, 'sed -i s/FIRESIM_CONFIG/{}/g sim/run_sim.sh'.format(hwconf.name))

    # Finally, tar it up
    rootLogger.info("Creating distributable package...")
    local_logged(swdir + '/../', 'rm -f {}.tgz && tar czvf {}.tgz sw/*'.format(swpkgname, swpkgname))
    rootLogger.info('Package created at {}.tgz'.format(ddir + '/results-build/' + builddir + swpkgname))

    aws = conf.enable_aws
    if aws:
        rootLogger.info("Copying to AWS S3 Bucket...")
        s3path = 's3://{}/swpkgs/{}.tgz'.format(s3bucket, swpkgname)
        local_logged(swdir + '/../', 'aws s3 cp {}.tgz {}'.format(swpkgname, s3path))
        rootLogger.info('Successfully copied to {}'.format(s3path))
    else:
        rootLogger.info("AWS disabled by configuration. You can manually copy the software package to AWS from this path:")
        rootLogger.info("{}".format(ddir + '/results-build/' + builddir + swpkgname))


@parallel
def local_build(global_build_config):
    """ Run Vivado, convert tar -> AGFI/AFI. Runs locally
    conf = buildconfig dicitonary
    """

    rootLogger.info("Running process to build AGFI from verilog.")

    # First, Produce dcp/tar for design. Runs on remote machines, out of
    # /home/centos/firesim-build/ """
    ddir = get_deploy_dir()
    builds = global_build_config.get_builds_list()
    buildconfig = builds[0]
    builddir = buildconfig.get_build_dir_name()
    # local AWS build directory; might have config-specific changes to fpga flow
    # When using sibling docker method, need to give true host path to firesim rather than our fake path
    firesimdir = os.getenv('FIRESIM_HOST_PATH') or ddir + '/../'
    fpgabuilddir = "hdk/cl/developer_designs/cl_" + buildconfig.get_chisel_triplet()
    remotefpgabuilddir = "hdk/cl/developer_designs/cl_firesim"

    # run the Vivado build
    with prefix('cd ' + ddir + '/../platforms/f1/aws-fpga'), \
         InfoStreamLogger('stdout'), InfoStreamLogger('stderr'):
        local('sudo docker run --mac-address="00:4E:01:B6:DD:79" -v ' + firesimdir +
        ':/firesim artifactory.galois.com:5008/firesim:bitstream_gen /bin/bash -c "cd /firesim/platforms/f1/aws-fpga; source hdk_setup.sh; export CL_DIR=/firesim/platforms/f1/aws-fpga/' + fpgabuilddir +
        '; cd \$CL_DIR/build/scripts/; ./aws_build_dcp_from_cl.sh -foreground -ignore_memory_requirement"', shell=get_local_shell())

    # rsync in the reverse direction to get build results
    local('cp -R {}/../platforms/f1/aws-fpga/{}/* {}/results-build/{}/'.format(ddir, fpgabuilddir, ddir, builddir))

    # next, do tar -> AGFI
    # This is done on the local copy
    afi = None
    agfi = None
    s3bucket = global_build_config.s3_bucketname
    afiname = buildconfig.name

    # construct the "tags" we store in the AGFI description
    tag_buildtriplet = buildconfig.get_chisel_triplet()
    tag_deploytriplet = tag_buildtriplet
    if buildconfig.deploytriplet != "None":
        tag_deploytriplet = buildconfig.deploytriplet

    # the asserts are left over from when we tried to do this with tags
    # - technically I don't know how long these descriptions are allowed to be,
    # but it's at least 256*3, so I'll leave these here for now as sanity
    # checks.
    assert len(tag_buildtriplet) <= 255, "ERR: aws does not support tags longer than 256 chars for buildtriplet"
    assert len(tag_deploytriplet) <= 255, "ERR: aws does not support tags longer than 256 chars for deploytriplet"

    with StreamLogger('stdout'), StreamLogger('stderr'):
        is_dirty_str = local("if [[ $(git status --porcelain) ]]; then echo '-dirty'; fi", capture=True)
        hash = local("git rev-parse HEAD", capture=True)
    tag_fsimcommit = hash + is_dirty_str

    assert len(tag_fsimcommit) <= 255, "ERR: aws does not support tags longer than 256 chars for fsimcommit"

    # construct the serialized description from these tags.
    description = firesim_tags_to_description(tag_buildtriplet, tag_deploytriplet, tag_fsimcommit)

    # Check if AWS is enabled
    aws = global_build_config.enable_aws 
        
    # if we're unlucky, multiple vivado builds may launch at the same time. so we
    # append the build node IP + a random string to diff them in s3
    global_append = "-localbuild-" + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10)) + ".tar"

    with prefix("""cd {}/results-build/{}/build/checkpoints/to_aws/""".format(ddir, builddir)), StreamLogger('stdout'), StreamLogger('stderr'):
        files = local('ls *.tar', capture=True)
        rootLogger.debug(files)
        rootLogger.debug(files.stderr)
        tarfile = files.split()[-1]
        s3_tarfile = tarfile + global_append
        if aws:
            localcap = local('aws s3 cp ' + tarfile + ' s3://' + s3bucket + '/dcp/' + s3_tarfile, capture=True)
            rootLogger.debug(localcap)
            rootLogger.debug(localcap.stderr)
            agfi_afi_ids = local("""aws ec2 create-fpga-image --input-storage-location Bucket={},Key={} --logs-storage-location Bucket={},Key={} --name "{}" --description "{}" """.format(s3bucket, "dcp/" + s3_tarfile, s3bucket, "logs/", afiname, description), capture=True)
            rootLogger.debug(agfi_afi_ids)
            rootLogger.debug(agfi_afi_ids.stderr)
            rootLogger.debug("create-fpga-image result: " + str(agfi_afi_ids))
            ids_as_dict = json.loads(agfi_afi_ids)
            agfi = ids_as_dict["FpgaImageGlobalId"]
            afi = ids_as_dict["FpgaImageId"]
            rootLogger.info("Resulting AGFI: " + str(agfi))
            rootLogger.info("Resulting AFI: " + str(afi))
        else:
            rootLogger.info("")
            rootLogger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            rootLogger.info("!! AWS disabled by configuration.                  !!")
            rootLogger.info("!! Not uploading checkpoint to S3 or creating AFI. !!")
            rootLogger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            rootLogger.info("")
            rootLogger.info("To create an AFI, copy the file below to S3:")
            rootLogger.info("File to Copy: firesim/deploy/results-build/{}/build/checkpoints/to_aws/{}".format(builddir, tarfile))
            rootLogger.info("")
            rootLogger.info("Example of copying to S3 bucket:")
            rootLogger.info("Command: aws s3 cp {} s3://mys3bucket/dcp/{}".format(tarfile, s3_tarfile))
            rootLogger.info("")
            rootLogger.info("Then have AWS create the AFI:")
            rootLogger.info("Command: aws ec2 create-fpga-image --input-storage-location Bucket=mys3bucket,Key=dcp/{} --logs-storage-location Bucket=mys3bucket,Key=logs/ --name \"{}\"".format(s3_tarfile, afiname))
            rootLogger.info("")
            rootLogger.info("The output of that command will contain the AGFI and AFI for your chosen region")
            rootLogger.info("Local build complete - please finish generating the AFI using an AWS-connected machine")
            rootLogger.info("")
            rootLogger.info("")


    # skip the remainder of the script if not using AWS
    if not aws:
        return

    rootLogger.info("Waiting for create-fpga-image completion.")
    results_build_dir = """{}/results-build/{}/""".format(ddir, builddir)
    with lcd(results_build_dir), StreamLogger('stdout'), StreamLogger('stderr'):
        checkstate = "pending"
        while checkstate == "pending":
            imagestate = local("""aws ec2 describe-fpga-images --fpga-image-id {} | tee AGFI_INFO""".format(afi), capture=True)
            state_as_dict = json.loads(imagestate)
            checkstate = state_as_dict["FpgaImages"][0]["State"]["Code"]
            rootLogger.info("Current state: " + str(checkstate))
            time.sleep(10)

    # copy the image to all regions for the current user
    copy_afi_to_all_regions(afi)

    message_title = "FireSim FPGA Build Completed"
    agfi_entry = "[" + afiname + "]\nagfi=" + agfi + "\ndeploytripletoverride=None\ncustomruntimeconfig=None\n\n"
    message_body = "Your AGFI has been created!\nAdd\n" + agfi_entry + "\nto your config_hwdb.ini to use this hardware configuration."

    send_firesim_notification(message_title, message_body)

    rootLogger.info(message_title)
    rootLogger.info(message_body)

    # for convenience when generating a bunch of images. you can just
    # cat all the files in this directory after your builds finish to get
    # all the entries to copy into config_hwdb.ini
    hwdb_entry_file_location = """{}/built-hwdb-entries/""".format(ddir)
    local("mkdir -p " + hwdb_entry_file_location)
    with open(hwdb_entry_file_location + "/" + afiname, "w") as outputfile:
        outputfile.write(agfi_entry)

    if global_build_config.post_build_hook:
        with StreamLogger('stdout'), StreamLogger('stderr'):
            localcap = local("""{} {}""".format(global_build_config.post_build_hook,
                                                results_build_dir,
                                                capture=True))
            rootLogger.debug("[localhost] " + str(localcap))
            rootLogger.debug("[localhost] " + str(localcap.stderr))

    rootLogger.info("Build complete! AFI ready. See AGFI_INFO.")

