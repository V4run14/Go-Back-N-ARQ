"""
Compute average delay per MSS from a Task 2 CSV and generate a plot.

CSV format expected: columns `mss`, `trial`, `seconds` (as written by
task2_remote.py).

Usage:
    python plot_task2.py --input task2_remote.csv --output task2_plot.png
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
                m = int(row["mss"])
                t = float(row["seconds"])
            except (KeyError, ValueError):
                continue
            buckets[m].append(t)
    averages = []
    for m in sorted(buckets.keys()):
        vals = buckets[m]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        averages.append((m, avg))
    return averages


def plot_averages(averages, out_path: Path):
    x = [m for m, _ in averages]
    y = [avg for _, avg in averages]
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o")
    plt.xlabel("MSS (bytes)")
    plt.ylabel("Average Delay (s)")
    plt.title("Task 2: Average Delay vs MSS")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Plot average delay vs MSS from Task 2 CSV.")
    parser.add_argument("--input", type=Path, default=Path("task2_remote.csv"),
                        help="CSV file with columns mss, trial, seconds.")
    parser.add_argument("--output", type=Path, default=Path("task2_plot.png"),
                        help="Output PNG path.")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"CSV not found: {args.input}")

    averages = compute_averages(args.input)
    if not averages:
        raise SystemExit("No data found in CSV.")

    print("Averages:")
    for m, avg in averages:
        print(f"MSS={m}: {avg:.3f}s")

    out_path = plot_averages(averages, args.output)
    print(f"Plot saved to {out_path.resolve()}")


if __name__ == "__main__":
    main()
