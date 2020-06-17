//See LICENSE for license details
package firesim.bridges

import midas.widgets._
import chisel3._
import chisel3.util._
import freechips.rocketchip.config.Parameters
import freechips.rocketchip.devices.debug.{DMIIO, DMIReq, DMIResp, DebugModuleKey}

// DOC include start: DMI Bridge Target-Side Interface
class DMIBridgeTargetIO(implicit p: Parameters) extends Bundle {
  val dmi = new DMIIO()
  val dbg_connected = Output(Bool())
  val dbg_memloaded = Input(Bool())
}
// DOC include end: DMI Bridge Target-Side Interface

case class DMIBridgeKey(mmInt: Boolean)

// DOC include start: DMI Bridge Target-Side Module
class DMIBridge(mmInt: Boolean = false)(implicit p: Parameters) extends BlackBox
    with Bridge[HostPortIO[DMIBridgeTargetIO], DMIBridgeModule] {
  // Since we're extending BlackBox this is the port will connect to in our target's RTL
  val io = IO(new DMIBridgeTargetIO)
  // Implement the bridgeIO member of Bridge using HostPort. This indicates that
  // we want to divide io, into a bidirectional token stream with the input
  // token corresponding to all of the inputs of this BlackBox, and the output token consisting of 
  // all of the outputs from the BlackBox
  val bridgeIO = HostPort(io)

  // And then implement the constructorArg member
  val constructorArg = Some(DMIBridgeKey(mmInt))

  // Finally, and this is critical, emit the Bridge Annotations -- without
  // this, this BlackBox would appear like any other BlackBox to golden-gate
  generateAnnotations()
}
// DOC include end: DMI Bridge Target-Side Module

// DOC include start: DMI Bridge Companion Object
object DMIBridge {
  def apply(dmi: DMIIO, mmInt: Boolean)(implicit p: Parameters): DMIBridge = {
    val ep = Module(new DMIBridge(mmInt))
    dmi <> ep.io.dmi
    ep
  }
}
// DOC include end: DMI Bridge Companion Object

// DOC include start: DMI Bridge Header
class DMIBridgeModule(bridgeKey: DMIBridgeKey)(implicit p: Parameters) extends BridgeModule[HostPortIO[DMIBridgeTargetIO]]()(p) {
  val io = IO(new WidgetIO())

  // This creates the host-side interface of your TargetIO
  val hPort = IO(HostPort(new DMIBridgeTargetIO))

  // Generate some FIFOs to capture tokens...
  val reqfifo = Module(new Queue(new DMIReq(p(DebugModuleKey).get.nDMIAddrSize), 8))
  val respfifo = Module(new Queue(new DMIResp, 8))

  val target = hPort.hBits.dmi
  val fire = hPort.toHost.hValid   && // We have a valid input token: toHost ~= leaving the transformed RTL
             hPort.fromHost.hReady && // We have space to enqueue a new output token
             respfifo.io.enq.ready    // We have space to capture new Response data
  hPort.toHost.hReady := fire
  hPort.fromHost.hValid := fire

  target.req.bits <> reqfifo.io.deq.bits
  reqfifo.io.deq.ready := target.req.ready && fire
  target.req.valid := reqfifo.io.deq.valid

  respfifo.io.enq.bits <> target.resp.bits
  respfifo.io.enq.valid := target.resp.valid && fire
  target.resp.ready := respfifo.io.enq.ready

  // General MMIO Registers
  val connected = RegInit(false.B)
  val memloaded = RegInit(false.B)
  hPort.hBits.dbg_connected := connected
  memloaded := hPort.hBits.dbg_memloaded
  genWOReg(connected, "connected")
  genROReg(memloaded, "memloaded")

  // Response MMIO registers
  genROReg(respfifo.io.deq.bits.data, "resp_data")
  genROReg(respfifo.io.deq.bits.resp, "resp")
  genROReg(respfifo.io.deq.valid, "resp_valid")
  Pulsify(genWORegInit(respfifo.io.deq.ready, "resp_ready", false.B), pulseLength = 1)

//  when (target.resp.valid) {
//    printf("DMI - RESP - Valid: data = 0x%x | resp = 0x%x\n", target.resp.bits.data, target.resp.bits.resp)
//  }

  // Request MMIO Registers
  genWOReg(reqfifo.io.enq.bits.addr, "req_addr")
  genWOReg(reqfifo.io.enq.bits.data, "req_data")
  genWOReg(reqfifo.io.enq.bits.op, "req_op")
  Pulsify(genWORegInit(reqfifo.io.enq.valid, "req_valid", false.B), pulseLength = 1)
  genROReg(reqfifo.io.enq.ready, "req_ready")
//  when (target.req.valid && fire) {
//    printf("DMI - REQ - Valid: addr = 0x%x | data = 0x%x | op = 0x%x\n", target.req.bits.addr, target.req.bits.data, target.req.bits.op)
//  }

  genCRFile()

  override def genHeader(base: BigInt, sb: StringBuilder) {
    super.genHeader(base, sb)
    sb.append(CppGenerationUtils.genMacro(s"${getWName.toUpperCase}_mmint_present", UInt32(if (bridgeKey.mmInt) 1 else 0)))
  }
}
