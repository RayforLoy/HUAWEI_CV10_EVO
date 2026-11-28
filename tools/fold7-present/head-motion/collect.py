import argparse
from collections import Counter
from pathlib import Path
import re
import shlex
import statistics
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument('serial')
parser.add_argument('label')
parser.add_argument('--seconds', type=int, default=60)
parser.add_argument('--cv10-only', action='store_true')
parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
adb = ['adb', '-s', args.serial]
if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label) or not 1 <= args.seconds <= 600:
    parser.error("use a simple label and a duration between 1 and 600 seconds")
out_dir = args.output_dir
out_dir.mkdir(parents=True, exist_ok=True)
layers = subprocess.check_output(adb + ['shell', 'dumpsys SurfaceFlinger --list'], text=True)
pocket = re.findall(r'RequestedLayerState\{([^\r\n]*SurfaceView\[org\.cv10\.pocketxr/[^\r\n]*\(BLAST\)#\d+) parentId=', layers)
cv10 = re.findall(r'RequestedLayerState\{([^\r\n]* SurfaceView\[\]@0\(BLAST\)#\d+) parentId=', layers)
if (not args.cv10_only and len(pocket) != 1) or len(cv10) != 1:
    raise SystemExit('Expected one active Pocket XR layer and one CV10 layer')

pocket_command = '' if args.cv10_only else f'echo POCKET\ndumpsys SurfaceFlinger --latency {shlex.quote(pocket[0])}'

remote_script = f'''gpu=/sys/class/kgsl/kgsl-3d0
for i in $(seq {args.seconds}); do
    printf 'SAMPLE '
    date '+%H:%M:%S.%N'
    printf 'GPU '
    read busy rest < "$gpu/gpu_busy_percentage"
    read current < "$gpu/devfreq/cur_freq"
    read cap < "$gpu/devfreq/max_freq"
    printf '%s %s %s\\n' "$busy" "$current" "$cap"
    {pocket_command}
    echo CV10
    dumpsys SurfaceFlinger --latency {shlex.quote(cv10[0])}
    sleep 0.85
done
'''


def describe(times):
    unique = sorted(set(times))
    if len(unique) < 2:
        return 'missing'
    intervals = [(end - start) / 1_000_000 for start, end in zip(unique, unique[1:])]
    intervals.sort()
    missed = sum(max(0, round(interval / (1000 / 90)) - 1) for interval in intervals)
    return (
        f'{(len(unique) - 1) * 1000 / sum(intervals):.1f}/s '
        f'p50={statistics.median(intervals):.1f}ms '
        f'p99={intervals[min(len(intervals) - 1, int(len(intervals) * 0.99))]:.1f}ms '
        f'max={max(intervals):.1f}ms missed={missed}'
    )


summary_path = out_dir / f'{args.label}-cadence.txt'
raw_path = out_dir / f'{args.label}-raw.txt'
sample = None
gpu = ''
readings = {}
current_layer = ''

with raw_path.open('w', encoding='utf-8') as raw, summary_path.open('w', encoding='utf-8') as summary:
    with subprocess.Popen(adb + ['shell', remote_script], stdout=subprocess.PIPE, text=True) as recording:
        for line in recording.stdout:
            raw.write(line)
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'SAMPLE':
                if sample is not None:
                    print(f'{sample} {gpu}  pocket={describe(readings["POCKET"])}  cv10={describe(readings["CV10"])}', file=summary, flush=True)
                sample = fields[1]
                readings = {'POCKET': [], 'CV10': []}
                current_layer = ''
            elif fields[0] == 'GPU':
                gpu = ' '.join(fields)
            elif fields[0] in readings:
                current_layer = fields[0]
            elif current_layer and len(fields) == 3:
                timestamp = int(fields[1])
                if 0 < timestamp < 2**63 - 1:
                    readings[current_layer].append(timestamp)
        if recording.wait() != 0:
            raise SystemExit('Device sampling command failed')

print(summary_path)
