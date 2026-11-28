#!/usr/bin/env python3
"""Measure phone and CV10 DRM retire cadence over the same Perfetto interval."""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import json
from math import ceil, isfinite
from pathlib import Path

from perfetto.trace_processor import TraceProcessor


SECOND_NS = 1_000_000_000
RETIRES_SQL = """
SELECT thread.name AS worker, slice.ts + slice.dur AS retire_ns
FROM slice JOIN thread_track ON thread_track.id = slice.track_id
JOIN thread USING (utid)
WHERE slice.name = 'signal_retire_fence' AND slice.dur >= 0
    AND thread.name GLOB 'crtc_event:[0-9]*'
ORDER BY retire_ns
"""
TRACE_LOSS_SQL = """
SELECT name, idx, value FROM stats WHERE severity = 'data_loss' AND value <> 0
UNION ALL
SELECT finish.name, finish.idx, finish.value - COALESCE(initial.value, 0)
FROM stats AS finish LEFT JOIN stats AS initial
    ON initial.name = 'ftrace_cpu_overrun_begin' AND initial.idx = finish.idx
WHERE finish.name = 'ftrace_cpu_overrun_end' AND finish.severity <> 'data_loss'
    AND finish.value > COALESCE(initial.value, 0)
ORDER BY name, idx
"""


def summarize_retires(timestamps, start_ns, end_ns, nominal_hz):
    inside = timestamps[bisect_left(timestamps, start_ns):bisect_left(timestamps, end_ns)]
    unique = sorted(set(inside))
    gaps = sorted(after - before for before, after in zip(unique, unique[1:]))
    late_gap_ns = 1.5 * SECOND_NS / nominal_hz
    full_seconds = (end_ns - start_ns) // SECOND_NS
    frames_by_second = Counter((stamp - start_ns) // SECOND_NS for stamp in unique)
    return {
        "nominal_hz": nominal_hz,
        "distinct_retires": len(unique),
        "duplicate_timestamps": len(inside) - len(unique),
        "retires_per_second": round(len(unique) * SECOND_NS / (end_ns - start_ns), 3),
        "per_full_second": [frames_by_second[i] for i in range(full_seconds)],
        "gaps_above_1_5_periods": sum(gap > late_gap_ns for gap in gaps),
        "gap_p95_ms": round(gaps[ceil(len(gaps) * 0.95) - 1] / 1e6, 3) if gaps else None,
        "gap_max_ms": round(gaps[-1] / 1e6, 3) if gaps else None,
        "start_to_first_ms": round((unique[0] - start_ns) / 1e6, 3) if unique else None,
        "last_to_end_ms": round((end_ns - unique[-1]) / 1e6, 3) if unique else None,
    }


def positive(value):
    number = float(value)
    if not isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("expected a finite positive number")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--phone-crtc", type=int, required=True)
    parser.add_argument("--cv10-crtc", type=int, required=True)
    parser.add_argument("--phone-hz", type=positive, default=60.0)
    parser.add_argument("--cv10-hz", type=positive, default=90.0)
    parser.add_argument("--start-s", type=float, default=0.0, help="seconds after the trace starts")
    parser.add_argument("--duration-s", type=positive, help="omit to use the end of the trace")
    args = parser.parse_args()
    if not 0 <= args.start_s < float("inf"):
        parser.error("--start-s must be finite and nonnegative")
    if min(args.phone_crtc, args.cv10_crtc) < 0 or args.phone_crtc == args.cv10_crtc:
        parser.error("provide two different nonnegative DRM CRTC IDs")
    if not args.trace.is_file():
        parser.error(f"trace does not exist: {args.trace}")

    retires = defaultdict(list)
    with TraceProcessor(trace=str(args.trace)) as processor:
        bounds = next(iter(processor.query("SELECT start_ts, end_ts FROM trace_bounds")))
        for row in processor.query(RETIRES_SQL):
            retires[row.worker].append(row.retire_ns)
        loss = [{"name": row.name, "idx": row.idx, "value": row.value}
                for row in processor.query(TRACE_LOSS_SQL)]

    trace_seconds = (bounds.end_ts - bounds.start_ts) / SECOND_NS
    if args.start_s >= trace_seconds or (args.duration_s is not None and args.duration_s > trace_seconds):
        parser.error("the requested interval is beyond the trace end")
    start = bounds.start_ts + round(args.start_s * SECOND_NS)
    end = bounds.end_ts if args.duration_s is None else start + round(args.duration_s * SECOND_NS)
    if not start < end <= bounds.end_ts:
        parser.error("the requested interval is empty or beyond the trace end")
    phone = summarize_retires(retires.get(f"crtc_event:{args.phone_crtc}", []), start, end, args.phone_hz)
    cv10 = summarize_retires(retires.get(f"crtc_event:{args.cv10_crtc}", []), start, end, args.cv10_hz)
    print(json.dumps({
        "trace": args.trace.name,
        "window_start_ns": start,
        "window_end_ns": end,
        "trace_data_loss": loss,
        "workers_with_retire_events": sorted(retires),
        "phone": {"crtc": args.phone_crtc, **phone},
        "cv10": {"crtc": args.cv10_crtc, **cv10},
    }, indent=2))
    if loss or cv10["distinct_retires"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
