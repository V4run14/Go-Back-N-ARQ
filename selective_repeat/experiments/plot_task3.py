"""
Compute average delay per loss probability p from a Task 3 CSV and generate a plot.

CSV format expected: columns `loss`, `trial`, `seconds` (as written by
task3_remote.py).

Usage:
    python plot_task3.py --input task3_remote.csv --output task3_plot.png
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
                p = float(row["loss"])
                t = float(row["seconds"])
            except (KeyError, ValueError):
                continue
            buckets[p].append(t)
    averages = []
    for p in sorted(buckets.keys()):
        vals = buckets[p]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        averages.append((p, avg))
    return averages


def plot_averages(averages, out_path: Path):
    x = [p for p, _ in averages]
    y = [avg for _, avg in averages]
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o")
    plt.xlabel("Loss probability p")
    plt.ylabel("Average Delay (s)")
    plt.title("Task 3: Average Delay vs Loss Probability")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Plot average delay vs loss probability from Task 3 CSV.")
    parser.add_argument("--input", type=Path, default=Path("task3_remote.csv"),
                        help="CSV file with columns loss, trial, seconds.")
    parser.add_argument("--output", type=Path, default=Path("task3_plot.png"),
                        help="Output PNG path.")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"CSV not found: {args.input}")

    averages = compute_averages(args.input)
    if not averages:
        raise SystemExit("No data found in CSV.")

    print("Averages:")
    for p, avg in averages:
        print(f"p={p:.2f}: {avg:.3f}s")

    out_path = plot_averages(averages, args.output)
    print(f"Plot saved to {out_path.resolve()}")


if __name__ == "__main__":
    main()
