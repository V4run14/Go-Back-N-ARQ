"""
Task 1 experiment script: measure effect of window size N on transfer delay.

Runs the in-repo Go-Back-N client and server locally, varying N, with MSS and
loss probability fixed to the project spec for Task 1. Produces a CSV of trial
times and prints averages.

Example:
    python experiments/task1_window.py --file ../go_back_n/testfile.txt
"""
import argparse
import csv
import os
import random
import socket
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT = Path(__file__).resolve().parents[1]
GBN_PATH = ROOT / "go_back_n"
if str(GBN_PATH) not in sys.path:
    sys.path.insert(0, str(GBN_PATH))

from client import Client  # noqa: E402
from server import Server  # noqa: E402


WINDOW_SIZES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_server(server: Server):
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def ensure_file(path: Path, min_bytes: int) -> Path:
    """Create a dummy file >= min_bytes if the provided path is missing/too small."""
    if path.exists() and path.stat().st_size >= min_bytes:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(os.urandom(min_bytes))
    return path


def run_trial(input_file: Path, window_size: int, mss: int, loss_prob: float) -> float:
    """Run a single transfer trial and return elapsed seconds."""
    tmp_dir = TemporaryDirectory()
    tmp_path = Path(tmp_dir.name)
    outfile = tmp_path / "out.dat"
    port = free_udp_port()

    server = Server(address="127.0.0.1", port=port, mss=mss,
                    output_file=str(outfile), p=loss_prob)
    server_thread = threading.Thread(target=run_server, args=(server,),
                                     daemon=True)
    server_thread.start()
    time.sleep(0.05)  # small delay to ensure bind

    client = Client(address="0.0.0.0", port=0, server_name="127.0.0.1",
                    server_port_num=port, mss=mss, window_size=window_size)
    start = time.perf_counter()
    client.start(str(input_file))
    elapsed = time.perf_counter() - start

    server_thread.join(timeout=2.0)
    tmp_dir.cleanup()
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Run Task 1 window size experiments locally.")
    parser.add_argument("--file", type=Path, default=Path("data_1mb.bin"),
                        help="Path to file >=1MB to send (auto-generated if absent).")
    parser.add_argument("--trials", type=int, default=5,
                        help="Trials per window size.")
    parser.add_argument("--loss", type=float, default=0.05,
                        help="Packet loss probability p.")
    parser.add_argument("--mss", type=int, default=500,
                        help="Maximum segment size.")
    parser.add_argument("--output", type=Path, default=Path("task1_results.csv"),
                        help="CSV output path.")
    args = parser.parse_args()

    random.seed(42)
    input_file = ensure_file(args.file, 1024 * 1024)

    rows = []
    print(f"Running Task 1 with file={input_file}, MSS={args.mss}, loss={args.loss}")
    for n in WINDOW_SIZES:
        durations = []
        for trial in range(1, args.trials + 1):
            elapsed = run_trial(input_file, n, args.mss, args.loss)
            durations.append(elapsed)
            print(f"N={n} trial {trial}/{args.trials}: {elapsed:.3f}s")
            rows.append({"window_size": n, "trial": trial, "seconds": elapsed})
        avg = sum(durations) / len(durations)
        print(f"Average for N={n}: {avg:.3f}s")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["window_size", "trial", "seconds"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Results written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
