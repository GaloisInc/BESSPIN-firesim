import csv
import os
import re
import sys
import argparse
import glob

from itertools import product
from collections import defaultdict

DATA_RE = re.compile(r"^packet timestamp: (\d+), len: (\d+), sender: (\d+), receiver: (\d+)$")

def parse_log(f):
    data = []
    for line in f:
        match = DATA_RE.match(line.strip())
        if match:
            tss, lens, sender, receiver = match.groups()
            data.append((int(tss), int(lens), int(sender), int (receiver)))
    return data

def compute_bw(packet_data, timestep, freq, bitwidth):
    last_ts = packet_data[-1][0]
    last_node = 0
    end_ts = (last_ts // timestep) * timestep
    cycles = range(0, end_ts + 1, timestep)
    send_totals = defaultdict(lambda: defaultdict(int))
    recv_totals = defaultdict(lambda: defaultdict(int))

    for (ts, plen, psend, precv) in packet_data:
        send_totals[ts // timestep][psend] += plen
        recv_totals[ts // timestep][precv] += plen
        last_node = max(last_node, max(psend, precv))

    cycles_per_milli = freq * 1e6
    n = last_node + 1

    result = []

    for (i, cycle) in enumerate(cycles):
        millis = cycle / cycles_per_milli
        datarow = [millis]

        for node in range(0, n):
            send_total = send_totals[i][node]
            send_bw = (send_total * bitwidth) / (timestep / freq)
            datarow.append(send_bw)

            recv_total = recv_totals[i][node]
            recv_bw = (recv_total * bitwidth) / (timestep / freq)
            datarow.append(recv_bw)

        result.append(datarow)

    return n, result

def main():
    parser = argparse.ArgumentParser(description="Plot bandwidth over time")
    parser.add_argument("--timestep", dest="timestep", type=int,
                        default = 1000000,
                        help="Time window (in cycles) to measure point bandwidth")
    parser.add_argument("--freq", dest="freq", type=float,
                        default = 3.2, help = "Clock frequency (in GHz)")
    parser.add_argument("--bitwidth", dest="bitwidth", type=int,
                        default = 64, help = "Width of interface (in bits)")
    parser.add_argument("workdir", help="Working directory")
    args = parser.parse_args()

    switchlogs = glob.glob(os.path.join(args.workdir, "switch*/switchlog"))
    switchlogs.sort()

    for switchlog in switchlogs:
        switchname = os.path.basename(os.path.dirname(switchlog))
        switchnum = int(switchname[6:])
        outfile = os.path.join(args.workdir, "result{}.csv".format(switchnum))
        nnodes = 0

        with open(switchlog) as f:
            raw_data = parse_log(f)
            if len(raw_data) == 0:
                sys.stderr.write("Error: no data found\n")
                sys.exit(-1)

            nnodes, result = compute_bw(
                raw_data, args.timestep, args.freq, args.bitwidth)

        with open(outfile, "w") as f:
            writer = csv.writer(f)
            titles = ["Time (ms)"]

            for node in range(0, nnodes):
                titles.append("Send BW {}".format(node))
                titles.append("Recv BW {}".format(node))

            writer.writerow(titles)
            writer.writerows(
                [[str(f) for f in row] for row in result])

if __name__ == "__main__":
    main()
