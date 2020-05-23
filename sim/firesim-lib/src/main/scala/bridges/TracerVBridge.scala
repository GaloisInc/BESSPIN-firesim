//See LICENSE for license details
package firesim.bridges

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import freechips.rocketchip.config.{Parameters, Field}
import freechips.rocketchip.diplomacy.AddressSet
import freechips.rocketchip.util._
import freechips.rocketchip.rocket.TracedInstruction
import freechips.rocketchip.subsystem.RocketTilesKey
import freechips.rocketchip.tile.TileKey

import testchipip.{TraceOutputTop, DeclockedTracedInstruction, TracedInstructionWidths}

import midas.widgets._
import testchipip.{StreamIO, StreamChannel}
import junctions.{NastiIO, NastiKey}
import TokenQueueConsts._


case class TracerVKey(
  insnWidths: Seq[TracedInstructionWidths], // Widths of variable length fields in each TI
  vecSizes: Seq[Int] // The number of insns in each vec (= max insns retired at that core)
)

class TracerVBridge(traceProto: Seq[Vec[DeclockedTracedInstruction]]) extends BlackBox
    with Bridge[HostPortIO[TraceOutputTop], TracerVBridgeModule] {
  val io = IO(Flipped(new TraceOutputTop(traceProto)))
  val bridgeIO = HostPort(io)
  val constructorArg = Some(TracerVKey(io.getWidths, io.getVecSizes))
  generateAnnotations()
}

object TracerVBridge {
  def apply(port: TraceOutputTop)(implicit p:Parameters): Seq[TracerVBridge] = {
    val ep = Module(new TracerVBridge(port.getProto))
    ep.io <> port
    Seq(ep)
  }
}

class TracerVBridgeModule(key: TracerVKey)(implicit p: Parameters) extends BridgeModule[HostPortIO[TraceOutputTop]]()(p)
    with UnidirectionalDMAToHostCPU {
  val io = IO(new WidgetIO)
  val hPort = IO(HostPort(Flipped(TraceOutputTop(key.insnWidths, key.vecSizes))))

  val tFire = hPort.toHost.hValid && hPort.fromHost.hReady
  //trigger conditions
  val traces = hPort.hBits.traces.flatten
  private val pcWidth = 40 // Fix the pcWidth at 40 to match expectation of host-side Tracer software
  private val insnWidth = traces.map(_.insn.getWidth).max

  //Program Counter trigger value can be configured externally
  val hostTriggerPCWidthOffset = pcWidth - p(CtrlNastiKey).dataBits
  val hostTriggerPCLowWidth = if (hostTriggerPCWidthOffset > 0) p(CtrlNastiKey).dataBits else pcWidth
  val hostTriggerPCHighWidth = if (hostTriggerPCWidthOffset > 0) hostTriggerPCWidthOffset else 0

  val hostTriggerPCStartHigh = RegInit(0.U(hostTriggerPCHighWidth.W))
  val hostTriggerPCStartLow = RegInit(0.U(hostTriggerPCLowWidth.W))
  attach(hostTriggerPCStartHigh, "hostTriggerPCStartHigh", WriteOnly)
  attach(hostTriggerPCStartLow, "hostTriggerPCStartLow", WriteOnly)
  val hostTriggerPCStart = Cat(hostTriggerPCStartHigh, hostTriggerPCStartLow)
  val triggerPCStart = RegInit(0.U(pcWidth.W))
  triggerPCStart := hostTriggerPCStart

  val hostTriggerPCEndHigh = RegInit(0.U(hostTriggerPCHighWidth.W))
  val hostTriggerPCEndLow = RegInit(0.U(hostTriggerPCLowWidth.W))
  attach(hostTriggerPCEndHigh, "hostTriggerPCEndHigh", WriteOnly)
  attach(hostTriggerPCEndLow, "hostTriggerPCEndLow", WriteOnly)
  val hostTriggerPCEnd = Cat(hostTriggerPCEndHigh, hostTriggerPCEndLow)
  val triggerPCEnd = RegInit(0.U(pcWidth.W))
  triggerPCEnd := hostTriggerPCEnd

  //Cycle count trigger
  val hostTriggerCycleCountWidthOffset = 64 - p(CtrlNastiKey).dataBits
  val hostTriggerCycleCountLowWidth = if (hostTriggerCycleCountWidthOffset > 0) p(CtrlNastiKey).dataBits else 64
  val hostTriggerCycleCountHighWidth = if (hostTriggerCycleCountWidthOffset > 0) hostTriggerCycleCountWidthOffset else 0

  val hostTriggerCycleCountStartHigh = RegInit(0.U(hostTriggerCycleCountHighWidth.W))
  val hostTriggerCycleCountStartLow = RegInit(0.U(hostTriggerCycleCountLowWidth.W))
  attach(hostTriggerCycleCountStartHigh, "hostTriggerCycleCountStartHigh", WriteOnly)
  attach(hostTriggerCycleCountStartLow, "hostTriggerCycleCountStartLow", WriteOnly)
  val hostTriggerCycleCountStart = Cat(hostTriggerCycleCountStartHigh, hostTriggerCycleCountStartLow)
  val triggerCycleCountStart = RegInit(0.U(64.W))
  triggerCycleCountStart := hostTriggerCycleCountStart

  val hostTriggerCycleCountEndHigh = RegInit(0.U(hostTriggerCycleCountHighWidth.W))
  val hostTriggerCycleCountEndLow = RegInit(0.U(hostTriggerCycleCountLowWidth.W))
  attach(hostTriggerCycleCountEndHigh, "hostTriggerCycleCountEndHigh", WriteOnly)
  attach(hostTriggerCycleCountEndLow, "hostTriggerCycleCountEndLow", WriteOnly)
  val hostTriggerCycleCountEnd = Cat(hostTriggerCycleCountEndHigh, hostTriggerCycleCountEndLow)
  val triggerCycleCountEnd = RegInit(0.U(64.W))
  triggerCycleCountEnd := hostTriggerCycleCountEnd

  val trace_cycle_counter = RegInit(0.U(64.W))

  //target instruction type trigger (trigger through target software)
  //can configure the trigger instruction type externally though simulation driver
  val hostTriggerStartInst = RegInit(0.U(insnWidth.W))
  val hostTriggerStartInstMask = RegInit(0.U(insnWidth.W))
  attach(hostTriggerStartInst, "hostTriggerStartInst", WriteOnly)
  attach(hostTriggerStartInstMask, "hostTriggerStartInstMask", WriteOnly)

  val hostTriggerEndInst = RegInit(0.U(insnWidth.W))
  val hostTriggerEndInstMask = RegInit(0.U(insnWidth.W))
  attach(hostTriggerEndInst, "hostTriggerEndInst", WriteOnly)
  attach(hostTriggerEndInstMask, "hostTriggerEndInstMask", WriteOnly)

  //trigger selector
  val triggerSelector = RegInit(0.U((p(CtrlNastiKey).dataBits).W))
  attach(triggerSelector, "triggerSelector", WriteOnly)

  //set the trigger
  //assert(triggerCycleCountEnd >= triggerCycleCountStart)
  val triggerCycleCountVal = RegInit(false.B)
  triggerCycleCountVal := (trace_cycle_counter >= triggerCycleCountStart) & (trace_cycle_counter <= triggerCycleCountEnd)

  val triggerPCValVec = RegInit(VecInit(Seq.fill(traces.length)(false.B)))
  traces.zipWithIndex.foreach { case (trace, i) =>
    when (trace.valid) {
      when (triggerPCStart === trace.iaddr) {
        triggerPCValVec(i) := true.B
      } .elsewhen ((triggerPCEnd === trace.iaddr) && triggerPCValVec(i)) {
        triggerPCValVec(i) := false.B
      }
    }
  }

  val triggerInstValVec = RegInit(VecInit(Seq.fill(traces.length)(false.B)))
  traces.zipWithIndex.foreach { case (trace, i) =>
    when (trace.valid) {
      when (!((hostTriggerStartInst ^ trace.insn) & hostTriggerStartInstMask).orR) {
        triggerInstValVec(i) := true.B
      } .elsewhen (!((hostTriggerEndInst ^ trace.insn) & hostTriggerEndInstMask).orR) {
        triggerInstValVec(i) := false.B
      }
    }
  }

  val trigger = MuxLookup(triggerSelector, false.B, Seq(
    0.U -> true.B,
    1.U -> triggerCycleCountVal,
    2.U -> triggerPCValVec.reduce(_ || _),
    3.U -> triggerInstValVec.reduce(_ || _)))

  //TODO: for inter-widget triggering
  //io.trigger_out.head <> trigger
  if (p(midas.TraceTrigger)) {
    BoringUtils.addSource(trigger, s"trace_trigger")
  }

  // DMA mixin parameters
  lazy val toHostCPUQueueDepth  = TOKEN_QUEUE_DEPTH
  lazy val dmaSize = BigInt((BIG_TOKEN_WIDTH / 8) * TOKEN_QUEUE_DEPTH)

  // Pad the iaddr to 40-bits to fix compatibility with host-side software
  val uint_traces = (traces map (trace => Cat(trace.valid, trace.iaddr.pad(40)).pad(64))).reverse
  outgoingPCISdat.io.enq.bits := Cat(Cat(trace_cycle_counter,
                                         0.U((outgoingPCISdat.io.enq.bits.getWidth - Cat(uint_traces).getWidth - trace_cycle_counter.getWidth).W)),
                                     Cat(uint_traces))

  val tFireHelper = DecoupledHelper(outgoingPCISdat.io.enq.ready, hPort.toHost.hValid)
  hPort.toHost.hReady := tFireHelper.fire(hPort.toHost.hValid)
  // We don't drive tokens back to the target.
  hPort.fromHost.hValid := true.B

  outgoingPCISdat.io.enq.valid := tFireHelper.fire(outgoingPCISdat.io.enq.ready, trigger)

  when (tFireHelper.fire) {
    trace_cycle_counter := trace_cycle_counter + 1.U
  }

  // This need to go on a debug switch
  //when (outgoingPCISdat.io.enq.fire()) {
  //  hPort.hBits.traces.zipWithIndex.foreach({ case (bundle, bIdx) =>
  //    printf("Tile %d Trace Bundle\n", bIdx.U)
  //    bundle.zipWithIndex.foreach({ case (insn, insnIdx) =>
  //      printf(p"insn ${insnIdx}: ${insn}\n")
  //      //printf(b"insn ${insnIdx}, valid: ${insn.valid}")
  //      //printf(b"insn ${insnIdx}, iaddr: ${insn.iaddr}")
  //      //printf(b"insn ${insnIdx}, insn: ${insn.insn}")
  //      //printf(b"insn ${insnIdx}, priv:  ${insn.priv}")
  //      //printf(b"insn ${insnIdx}, exception: ${insn.exception}")
  //      //printf(b"insn ${insnIdx}, interrupt: ${insn.interrupt}")
  //      //printf(b"insn ${insnIdx}, cause: ${insn.cause}")
  //      //printf(b"insn ${insnIdx}, tval: ${insn.tval}")
  //    })
  //  })
  //}
  attach(outgoingPCISdat.io.deq.valid && !outgoingPCISdat.io.enq.ready, "tracequeuefull", ReadOnly)
  genCRFile()
}
