import argparse
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
import re
from statistics import median, quantiles


ROOT = Path(__file__).resolve().parent
NS_PER_SECOND = 1_000_000_000
NS_PER_MILLISECOND = 1_000_000
TAG = re.compile(r"\bCV10_(POCKET_STAMP|DRAW|SOURCE|FEEDBACK|PRESENT|GPU) (.*)")
VALUE = re.compile(r"(\w+)=(-?\d+)(?: |$)")
SF_ROW = re.compile(r"\s*(\d+)\s+(\d+)\s+(\d+)\s*")


def rate(timestamps):
    unique = sorted(set(timestamps))
    return (len(unique) - 1) * NS_PER_SECOND / (unique[-1] - unique[0]) if len(unique) > 1 else 0


def print_stats(name, values):
    p50 = median(values)
    p95 = quantiles(values, n=20)[18]
    print(f"  {name}: {p50 / NS_PER_MILLISECOND:.2f} / {p95 / NS_PER_MILLISECOND:.2f} ms")


def report(label, log_dir, surfaceflinger_dir):
    log = (log_dir / f"{label}-submit.txt").read_text(encoding="utf-8-sig")
    start = int(re.search(r"CV10_BENCH start=(\d+)", log)[1])
    begin, end = start + 12 * NS_PER_SECOND, start + 27 * NS_PER_SECOND
    rows = defaultdict(dict)
    keys = {"POCKET_STAMP": "stamp", "SOURCE": "layer"}
    for kind, line in TAG.findall(log):
        values = {name: int(value) for name, value in VALUE.findall(line)}
        rows[kind][values[keys.get(kind, "id")]] = values

    sf_times = set()
    active = False
    for line in (surfaceflinger_dir / f"{label}-raw.txt").read_text(encoding="utf-8-sig").splitlines():
        if line in ("CV10", "POCKET"):
            active = line == "CV10"
        elif active and (match := SF_ROW.fullmatch(line)) and begin <= int(match[2]) < end:
            sf_times.add(int(match[2]))

    submitted = [value["end"] for value in rows["PRESENT"].values()
                 if value["result"] == 0 and begin <= value["end"] < end]
    feedback = sorted(rows["FEEDBACK"].items(), key=lambda item: item[1]["actual"])
    exact_matches = {value["actual"] for _, value in feedback} & sf_times
    swaps = sorted(entry["swap"] for entry in rows["POCKET_STAMP"].values())
    intervals = defaultdict(list)
    displayed_stamps = set()
    fresh_presents = []
    skipped_newer_swap = 0

    for frame_id, value in feedback:
        actual = value["actual"]
        if actual not in exact_matches:
            continue
        draw = rows["DRAW"].get(frame_id)
        if draw is None or frame_id not in rows["GPU"]:
            continue
        source = rows["SOURCE"].get(draw["layer"])
        if source is None or source["stamp"] not in rows["POCKET_STAMP"]:
            continue
        producer = rows["POCKET_STAMP"][source["stamp"]]
        swap, start_draw, gpu_end = producer["swap"], draw["at"], rows["GPU"][frame_id]["end"]
        if not swap <= start_draw <= gpu_end <= actual:
            continue

        intervals["Pocket swap to Monado draw"].append(start_draw - swap)
        intervals["Monado draw to GPU done"].append(gpu_end - start_draw)
        intervals["GPU done to CV10 present"].append(actual - gpu_end)
        intervals["Pocket swap to CV10 present"].append(actual - swap)
        if bisect_right(swaps, start_draw) > bisect_right(swaps, swap):
            skipped_newer_swap += 1
        if source["stamp"] not in displayed_stamps:
            displayed_stamps.add(source["stamp"])
            fresh_presents.append(actual)

    if not intervals:
        raise ValueError(f"No complete Pocket-to-CV10 timing samples in {label}")
    paired = len(intervals["Pocket swap to CV10 present"])
    print(label)
    print(f"  Monado {rate(submitted):.2f} submits/s; CV10 {rate(exact_matches):.2f} actual/s"
          f" ({len(exact_matches)}/{len(sf_times)} matching timestamps); fresh {rate(fresh_presents):.2f}/s")
    print(f"  Newer Pocket swap timestamps before draw: {skipped_newer_swap}/{paired} joins")
    for name, values in intervals.items():
        print_stats(name, values)


parser = argparse.ArgumentParser()
parser.add_argument("label", nargs="+")
parser.add_argument("--logs", type=Path, default=ROOT)
parser.add_argument("--surfaceflinger", type=Path, default=ROOT.parent / "head-motion")
args = parser.parse_args()
for label in args.label:
    report(label, args.logs, args.surfaceflinger)
