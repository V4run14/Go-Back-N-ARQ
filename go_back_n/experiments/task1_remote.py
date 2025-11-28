"""
Task 1 runner against a remote server.

Assumes server.py is already running on the remote host with:
    python3 server.py <port> <output_file> 0.05

This script runs the local client, sweeps window sizes N, performs multiple
trials per N, and writes per-trial timings to a CSV. It does NOT measure RTT
or produce plots—compute averages and plot from the CSV separately.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client import Client  # noqa: E402


WINDOW_SIZES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]


def main():
    parser = argparse.ArgumentParser(
        description="Run Task 1 (window sweep) against a remote server.")
    parser.add_argument("--host", default="152.7.177.56",
                        help="Remote server IP/hostname.")
    parser.add_argument("--port", type=int, default=7735,
                        help="Remote server UDP port.")
    parser.add_argument("--file", type=Path, default=Path("data_1mb.bin"),
                        help="Path to local file >=1MB to send.")
    parser.add_argument("--mss", type=int, default=500,
                        help="MSS to use for all runs (spec: 500).")
    parser.add_argument("--trials", type=int, default=5,
                        help="Trials per window size.")
    parser.add_argument("--output", type=Path, default=Path("task1_remote.csv"),
                        help="CSV output file.")
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"Input file not found: {args.file}")

    rows = []
    print(f"Running Task 1 remote sweep to {args.host}:{args.port}")
    print(f"File={args.file} MSS={args.mss} Trials={args.trials}")
    for n in WINDOW_SIZES:
        for trial in range(1, args.trials + 1):
            client = Client(address="0.0.0.0", port=0,
                            server_name=args.host, server_port_num=args.port,
                            mss=args.mss, window_size=n)
            start = time.perf_counter()
            client.start(str(args.file))
            elapsed = time.perf_counter() - start
            rows.append({"window_size": n, "trial": trial, "seconds": elapsed})
            print(f"N={n} trial {trial}/{args.trials}: {elapsed:.3f}s")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["window_size", "trial", "seconds"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote results to {args.output.resolve()}")


if __name__ == "__main__":
    main()
