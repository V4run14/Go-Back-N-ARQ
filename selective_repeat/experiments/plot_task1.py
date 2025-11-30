"""
Compute average delay per window size N from a Task 1 CSV and generate a plot.

CSV format expected: columns `window_size`, `trial`, `seconds` (as written by
task1_window.py or task1_remote.py).

Usage:
    python plot_task1.py --input task1_remote.csv --output task1_remote_plot.png
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def compute_averages(csv_path: Path):
    buckets = defaultdict(list)
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                n = int(row["window_size"])
                t = float(row["seconds"])
            except (KeyError, ValueError):
                continue
            buckets[n].append(t)
    averages = []
    for n in sorted(buckets.keys()):
        vals = buckets[n]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        averages.append((n, avg))
    return averages


def plot_averages(averages, out_path: Path, log_x=True):
    x = [n for n, _ in averages]
    y = [avg for _, avg in averages]
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o")
    if log_x:
        plt.xscale("log", base=2)
    plt.xlabel("Window Size N")
    plt.ylabel("Average Delay (s)")
    plt.title("Task 1: Average Delay vs Window Size")
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Plot average delay vs window size from Task 1 CSV.")
    parser.add_argument("--input", type=Path, default=Path("task1_remote.csv"),
                        help="CSV file with columns window_size, trial, seconds.")
    parser.add_argument("--output", type=Path, default=Path("task1_plot.png"),
                        help="Output PNG path.")
    parser.add_argument("--linear-x", action="store_true",
                        help="Use linear X axis instead of log2.")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"CSV not found: {args.input}")

    averages = compute_averages(args.input)
    if not averages:
        raise SystemExit("No data found in CSV.")

    print("Averages:")
    for n, avg in averages:
        print(f"N={n}: {avg:.3f}s")

    out_path = plot_averages(averages, args.output, log_x=not args.linear_x)
    print(f"Plot saved to {out_path.resolve()}")


if __name__ == "__main__":
    main()
