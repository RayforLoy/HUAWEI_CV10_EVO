import re
import subprocess
import sys
from pathlib import Path

src, stage, analyzer = map(Path, sys.argv[1:])
evidence = stage / "evidence"
summary = []
for log in sorted(src.glob("*-submit.txt")):
    if not (log.name.startswith("pocket-ready-cadence-pair") or log.name.startswith("pocket-budgeted-fence-matrix1-")):
        continue
    label = log.name.removesuffix("-submit.txt")
    sf = src.parent / "head-motion" / f"{label}-raw.txt"
    original = log.read_text(encoding="utf-8-sig")
    if not sf.is_file() or not re.search(r"CV10_BENCH start=(\d+)", original):
        continue
    entries = re.findall(r"(?m)\b(CV10_(?:BENCH|POCKET_STAMP|DRAW|SOURCE|FEEDBACK|PRESENT|GPU)) (.*)$", original)
    lines = [f"{tag} " + " ".join(re.findall(r"\b[a-zA-Z_]\w*=(?:-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false)(?= |$)", values)) for tag, values in entries]
    (evidence / "ffr-quad" / log.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = [line for line in sf.read_text(encoding="utf-8-sig").splitlines() if re.fullmatch(r"CV10|POCKET|SAMPLE [\d:.]+|GPU[ \d]+|\s*\d+\s+\d+\s+\d+\s*|\d+", line)]
    (evidence / "head-motion" / sf.name).write_text("\n".join(rows) + "\n", encoding="utf-8")
    result = subprocess.check_output([sys.executable, str(analyzer), label, "--logs", str(evidence / "ffr-quad"), "--surfaceflinger", str(evidence / "head-motion")], text=True)
    state = (src / f"{label}-state-before.txt").read_text(encoding="utf-8-sig")
    temps = re.findall(r"Thermal Status: \d+|mValue=\d+(?:\.\d+)?, mType=3, mName=SKIN, mStatus=\d+", state)
    battery = (src / f"{label}-battery.txt").read_text(encoding="utf-8-sig").strip()
    mode_file = src / f"{label}-mode.txt"
    states = re.findall(r"mCommittedState=(?:ON|OFF)|restored-panel", mode_file.read_text(encoding="utf-8-sig")) if mode_file.exists() else []
    waits = [int(value) for value in re.findall(r"\bfence_wait=(\d+)\b", "\n".join(lines)) if int(value)]
    wait = f"Nonzero optional waits in entire capture: {len(waits)}" + (f"; max {max(waits)/1000:.0f} us" if waits else "")
    summary.extend([result.rstrip(), f"  Pre-capture: {'; '.join(temps)}; {' '.join(battery.split())}", f"  Display power records: {' '.join(states)}", f"  {wait}", ""])
(evidence / "fold7-present-summary.txt").write_text("\n".join(summary), encoding="utf-8")
