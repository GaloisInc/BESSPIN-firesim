//See LICENSE for license details
package firesim.bridges

import midas.widgets._
import chisel3._
import chisel3.util._
import freechips.rocketchip.config.Parameters
import freechips.rocketchip.devices.debug.{DMIIO, DMIReq, DMIResp, DebugModuleKey}
//import freechips.rocketchip.subsystem.PeripheryBusKey
//import sifive.blocks.devices.uart.{PeripheryUARTKey, UARTParams, UARTPortIO}

// DOC include start: DMI Bridge Target-Side Interface
class DMIBridgeTargetIO()(implicit p: Parameters) extends Bundle {
  val dmi = new DMIIO()
  //val reset = Input(Bool())
}
// DOC include end: DMI Bridge Target-Side Interface

// DOC include start: DMI Bridge Target-Side Module
class DMIBridge(implicit p: Parameters) extends BlackBox
    with Bridge[HostPortIO[DMIBridgeTargetIO], DMIBridgeModule] {
  // Since we're extending BlackBox this is the port will connect to in our target's RTL
  val io = IO(new DMIBridgeTargetIO)
  // Implement the bridgeIO member of Bridge using HostPort. This indicates that
  // we want to divide io, into a bidirectional token stream with the input
  // token corresponding to all of the inputs of this BlackBox, and the output token consisting of 
  // all of the outputs from the BlackBox
  val bridgeIO = HostPort(io)

  // And then implement the constructorArg member
  val constructorArg = None

  // Finally, and this is critical, emit the Bridge Annotations -- without
  // this, this BlackBox would appear like any other BlackBox to golden-gate
  generateAnnotations()
}
// DOC include end: DMI Bridge Target-Side Module

// DOC include start: DMI Bridge Companion Object
object DMIBridge {
  def apply(dmi: DMIIO)(implicit p: Parameters): DMIBridge = {
    val ep = Module(new DMIBridge)
    dmi <> ep.io.dmi
    ep
  }
}
// DOC include end: DMI Bridge Companion Object

// DOC include start: DMI Bridge Header
// Our DMIBridgeModule definition, note:
// 1) it takes one parameter, key, of type UARTKey --> the same case class we captured from the target-side
// 2) It accepts one implicit parameter of type Parameters
// 3) It extends BridgeModule passing the type of the HostInterface
//
// While the scala-type system will check if you parameterized BridgeModule
// correctly, the types of the constructor arugument (in this case UARTKey),
// don't match, you'll only find out later when Golden Gate attempts to generate your module.
class DMIBridgeModule(implicit p: Parameters) extends BridgeModule[HostPortIO[DMIBridgeTargetIO]]()(p) {
  val io = IO(new WidgetIO())

  // This creates the host-side interface of your TargetIO
  val hPort = IO(HostPort(new DMIBridgeTargetIO))

  // Generate some FIFOs to capture tokens...
  val reqfifo = Module(new Queue(new DMIReq(p(DebugModuleKey).get.nDMIAddrSize), 8))
  val respfifo = Module(new Queue(new DMIResp, 8))

  val target = hPort.hBits.dmi
  // In general, your BridgeModule will not need to do work every host-cycle. In simple Bridges,
  // we can do everything in a single host-cycle -- fire captures all of the
  // conditions under which we can consume and input token and produce a new
  // output token
  val fire = hPort.toHost.hValid   && // We have a valid input token: toHost ~= leaving the transformed RTL
             hPort.fromHost.hReady && // We have space to enqueue a new output token
             respfifo.io.enq.ready    // We have space to capture new TX data
  hPort.toHost.hReady := fire
  hPort.fromHost.hValid := fire

  target.req.bits <> reqfifo.io.deq.bits
  reqfifo.io.deq.ready := target.req.ready && fire
  target.req.valid := reqfifo.io.deq.valid

  respfifo.io.enq.bits <> target.resp.bits
  respfifo.io.enq.valid := target.resp.valid && fire
  target.resp.ready := respfifo.io.enq.ready

  // DOC include start: DMI Bridge Footer
  // Exposed the head of the queue and the valid bit as a read-only registers
  // with name "out_bits" and out_valid respectively
  genROReg(respfifo.io.deq.bits.data, "resp_data")
  genROReg(respfifo.io.deq.bits.resp, "resp")
  genROReg(respfifo.io.deq.valid, "resp_valid")
  Pulsify(genWORegInit(respfifo.io.deq.ready, "resp_ready", false.B), pulseLength = 1)

//  when (target.resp.valid) {
//    printf("DMI - RESP - Valid: data = 0x%x | resp = 0x%x\n", target.resp.bits.data, target.resp.bits.resp)
//  }
  // Generate a writeable register, "out_ready", that when written to dequeues
  // a single element in the tx_fifo. Pulsify derives the register back to false
  // after pulseLength cycles to prevent multiple dequeues
  // Pulsify(genWORegInit(target.resp.ready, "resp_ready", false.B), pulseLength = 1)

  genWOReg(reqfifo.io.enq.bits.addr, "req_addr")
  genWOReg(reqfifo.io.enq.bits.data, "req_data")
  genWOReg(reqfifo.io.enq.bits.op, "req_op")
  Pulsify(genWORegInit(reqfifo.io.enq.valid, "req_valid", false.B), pulseLength = 1)
  genROReg(reqfifo.io.enq.ready, "req_ready")
//  when (target.req.valid && fire) {
//    printf("DMI - REQ - Valid: addr = 0x%x | data = 0x%x | op = 0x%x\n", target.req.bits.addr, target.req.bits.data, target.req.bits.op)
//  }

  // This method invocation is required to wire up all of the MMIO registers to
  // the simulation control bus (AXI4-lite)
  genCRFile()
  // DOC include end: DMI Bridge Footer
}
