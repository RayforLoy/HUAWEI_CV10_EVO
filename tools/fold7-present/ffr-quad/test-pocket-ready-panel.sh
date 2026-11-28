#!/system/bin/sh
set -eu
expected=$(dumpsys -t 1 SurfaceFlinger --display-id | sed -n 's/^Display \([0-9][0-9]*\).*displayName="HUAWEIAV03"$/\1/p')
[ -n "$expected" ] || exit 1
before=$(dumpsys -t 1 SurfaceFlinger --scheduler)
echo "$before" | grep -q "forcedPacesetterDisplayId=$expected$" || exit 1
trap 'cmd display power-reset 0 && echo restored-panel' EXIT
trap 'exit 0' TERM INT
cmd display power-off 0
echo "active pid=$$"
for tick in $(seq 55); do
    sleep 1
    charge=$(dumpsys -t 1 battery | sed -n 's/^[[:space:]]*level: \([0-9][0-9]*\)$/\1/p')
    [ "${charge:-0}" -ge 20 ] || break
done