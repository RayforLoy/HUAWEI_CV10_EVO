import argparse
from pathlib import Path
from perfetto.trace_processor import TraceProcessor

parser = argparse.ArgumentParser()
parser.add_argument("traces", type=Path, nargs="+")
parser.add_argument("--composer-pid", type=int)
args = parser.parse_args()
condition = f"process.pid={args.composer_pid}" if args.composer_pid is not None else "process.name LIKE '%composer%'"
for path in args.traces:
    print(path.name)
    with TraceProcessor(trace=str(path)) as trace:
        for query in [
            "SELECT name, COUNT(*) AS n FROM ftrace_event WHERE name LIKE '%contention%' OR name LIKE '%sys%ioctl%' OR name LIKE '%blocked_reason%' GROUP BY 1",
            "SELECT name, idx, value FROM stats WHERE (name LIKE '%ftrace%' OR name LIKE '%discard%') AND value>0 LIMIT 25",
            "SELECT thread.name AS thread, slice.name AS section, COUNT(*) AS n, ROUND(AVG(dur)/1000000.0,3) AS ms FROM slice JOIN thread_track ON thread_track.id=slice.track_id JOIN thread USING (utid) WHERE dur>0 AND (slice.name IN ('DRMAtomicReq::Commit::', 'atomic_commit', 'signal_retire_fence') OR slice.name LIKE 'HwcPresentOrValidateDisplay %') GROUP BY 1,2 ORDER BY 2,4 DESC",
            f"SELECT thread.name AS thread, state, blocked_function, COUNT(*) AS n FROM thread_state JOIN thread USING(utid) JOIN process USING(upid) WHERE {condition} AND blocked_function IS NOT NULL GROUP BY 1,2,3 LIMIT 15",
        ]:
            rows=list(trace.query(query))
            for row in rows: print(row)
            if not rows: print('<none>')