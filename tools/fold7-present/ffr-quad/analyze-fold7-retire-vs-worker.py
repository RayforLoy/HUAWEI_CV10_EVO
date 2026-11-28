import argparse
from pathlib import Path
from perfetto.trace_processor import TraceProcessor
q="""
WITH work AS (
  SELECT s.ts, s.ts+s.dur AS ends
  FROM slice AS s JOIN thread_track tt ON s.track_id=tt.id
  JOIN thread t USING(utid)
  WHERE t.name='crtc_commit:{crtc}' AND s.name='complete_commit' AND s.dur>0
), retire AS (
  SELECT s.ts+s.dur AS at
  FROM slice AS s JOIN thread_track tt ON s.track_id=tt.id
  JOIN thread t USING(utid)
  WHERE t.name='crtc_event:{crtc}' AND s.name='signal_retire_fence' AND s.dur>=0
), atomic_calls AS (
  SELECT s.ts,s.dur
  FROM slice s JOIN slice parent ON s.parent_id=parent.id
  JOIN thread_track tt ON s.track_id=tt.id JOIN thread t USING(utid)
  JOIN process p USING(upid)
  WHERE p.pid={composer_pid} AND t.name LIKE 'binder:%' AND s.name='atomic_commit' AND s.dur>0
    AND parent.name='DRMAtomicReq::Commit::'
), matched AS (
  SELECT work.*, (SELECT MAX(retire.at) FROM retire
      WHERE retire.at BETWEEN work.ts AND work.ends+1000000) AS signaled
  FROM work
)
SELECT COUNT(*) n, COUNT(signaled) matched,
    COUNT(*) FILTER (WHERE signaled<=ends) before_worker_end,
    MIN(ends-signaled)/1e6 earliest_end_ns, MAX(ends-signaled)/1e6 latest_end_ns,
    ROUND(AVG(ends-signaled)/1e6,3) avg_end_ms FROM matched;
"""
second=q[:q.index('SELECT COUNT(*) n')]+"""
SELECT COUNT(*) overlapping_calls,
       COUNT(*) FILTER (WHERE signaled>atomic_calls.ts) signaled_after_atomic_entry,
       COUNT(*) FILTER (WHERE signaled<=atomic_calls.ts) signaled_before_atomic_entry,
       ROUND(AVG(signaled-atomic_calls.ts)/1e6,3) mean_entry_to_retire_ms
FROM atomic_calls JOIN matched ON atomic_calls.ts BETWEEN matched.ts AND matched.ends
WHERE (SELECT COUNT(*) FROM matched w2 WHERE atomic_calls.ts BETWEEN w2.ts AND w2.ends)=1;
"""
parser = argparse.ArgumentParser()
parser.add_argument("traces", type=Path, nargs="+")
parser.add_argument("--crtc", type=int, required=True)
parser.add_argument("--composer-pid", type=int, required=True)
args = parser.parse_args()
params = dict(crtc=args.crtc, composer_pid=args.composer_pid)
for path in args.traces:
    with TraceProcessor(trace=str(path)) as trace:
        print(path.name, *trace.query(q.format(**params)), *trace.query(second.format(**params)))
