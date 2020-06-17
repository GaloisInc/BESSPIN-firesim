package firesim.bridges

import midas.widgets._

import chisel3._
import chisel3.util._
import freechips.rocketchip.config.Parameters
import ssith._

class RandomBridge extends BlackBox with Bridge[HostPortIO[RandomBridgeTargetIO], RandomBridgeModule] {
  val io = IO(new RandomBridgeTargetIO)
  val bridgeIO = HostPort(io)
  val constructorArg = None
  generateAnnotations()
}

object RandomBridge {
  def apply(port: RNGIO)(implicit p: Parameters): RandomBridge = {
    val ep = Module(new RandomBridge)
    ep.io.randOut <> port.randIn
    ep
  }
}

class RandomBridgeTargetIO extends Bundle {
  val randOut = DecoupledIO(UInt(32.W))
}

class RandomBridgeModule(implicit p: Parameters) extends BridgeModule[HostPortIO[RandomBridgeTargetIO]]()(p) {
  private val fifoSize = 128;
  require(fifoSize % 8 == 0, "Minimum FIFO size must be a non-zero multiple of 8")
  val io = IO(new WidgetIO)
  val hPort = IO(HostPort(new RandomBridgeTargetIO))

  val target = hPort.hBits.randOut
  val tFire = hPort.toHost.hValid && hPort.fromHost.hReady

  val thresholdReg = genWORegInit(Wire(UInt(32.W)), "threshold_value", (fifoSize/8).U(32.W))
  val buffer = Module(new Queue(UInt(32.W), fifoSize))
  val thresholdReached = thresholdReg > buffer.io.count
  buffer.reset  := reset.toBool

  hPort.toHost.hReady := tFire
  hPort.fromHost.hValid := tFire

  target.bits <> buffer.io.deq.bits
  buffer.io.deq.ready := target.ready && tFire
  target.valid := buffer.io.deq.valid

  genWOReg(buffer.io.enq.bits, "in_bits")
  Pulsify(genWORegInit(buffer.io.enq.valid, "in_valid", false.B), pulseLength = 1)
  genROReg(buffer.io.enq.ready, "in_ready")
  genROReg(thresholdReached, "threshold_reached")

  genCRFile()
}
