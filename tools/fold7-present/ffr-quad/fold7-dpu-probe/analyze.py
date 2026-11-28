from pathlib import Path
from statistics import median,quantiles
import re
from perfetto.trace_processor import TraceProcessor
for capture in sorted(Path(__file__).resolve().parent.glob("*.perfetto-trace")):
    print(capture.name)
    s=capture.with_suffix(".log").read_text()
    frames=[(int(i),int(q),int(p)) for i,q,p in re.findall(r"id=(\d+) queue=(\d+) present=(\d+)",s)]
    frames=[row for row in frames if 180<=row[0]<750]
    t=sorted({row[2] for row in frames})
    if len(t)>1:
        dt=[(b-a)/1e6 for a,b in zip(t,t[1:])]
        print(f"present callbacks={len(frames)} distinct={len(t)} rate={(len(t)-1)*1e9/(t[-1]-t[0]):.3f} times/s p50={median(dt):.3f}ms p95={quantiles(dt,n=20)[18]:.3f}ms")
    with TraceProcessor(trace=str(capture)) as tp:
        for row in tp.query("""
            SELECT EXTRACT_ARG(slice.arg_set_id, 'layer_name') AS layer,
                   COUNT(*) AS n,
                   ROUND(1e9 * (COUNT(DISTINCT slice.ts)-1) / (MAX(slice.ts)-MIN(slice.ts)),3) AS hz
            FROM slice JOIN track ON slice.track_id=track.id
            WHERE track.name LIKE 'Buffer: %' AND slice.name='PresentFenceSignaled'
            GROUP BY 1 ORDER BY n DESC LIMIT 6
        """):
            print(row)
        for row in tp.query("""
            SELECT t.name AS track, s.name, COUNT(*) AS n,
                   ROUND(1e9 * (COUNT(*) - 1) / (MAX(s.ts) - MIN(s.ts)),3) AS hz,
                   ROUND(AVG(s.dur)/1e6,3) AS avg_ms
            FROM slice s JOIN thread_track tt ON tt.id=s.track_id JOIN thread t USING(utid)
            WHERE s.dur>=0 AND (s.name GLOB 'HwcPresentOrValidateDisplay *'
                OR (s.name='signal_retire_fence' AND t.name GLOB 'crtc_event:*'))
            GROUP BY 1,2 ORDER BY 2,1
        """):
            print(row)
