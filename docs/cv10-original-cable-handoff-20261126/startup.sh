#!/system/bin/sh
# Run on the Fold7 with "adb -s <serial> shell sh .../startup.sh observe|delay".
mode=${1:-observe}
case "$mode" in observe|delay) ;; *) echo 'usage: startup.sh observe|delay' >&2; exit 2;; esac
[ "$(getprop ro.product.model)" = SM-F9660 ] || { echo 'Expected a Galaxy Z Fold7 SM-F9660' >&2; exit 2; }

log() { printf '%s %s\n' "$(date '+%T.%3N')" "$*"; }
cv10_id() {
  displays=$(cmd display get-displays) || return 1
  id=$(printf '%s\n' "$displays" | sed -n 's/^Display id \([0-9][0-9]*\): DisplayInfo{"HUAWEIAV03".*/\1/p')
  case "$id" in ''|0|*[!0-9]*) return 1;; esac
  printf '%s\n' "$id"
}
power_mode() {
  dumpsys SurfaceFlinger --displays | awk '
    /name="/ { remaining = ($0 ~ /name="HUAWEIAV03"/) ? 6 : 0 }
    remaining > 0 {
      if (/powerMode=/) { sub(/^.*powerMode=/,""); print $1; found=1; exit }
      remaining--
    }
    END { if (!found) print "unknown" }'
}
watch_usb() {
  previous=initial
  while :; do
    tree=$(ls -1 /sys/bus/usb/devices | tr '\n' ',')
    if [ "$tree" != "$previous" ]; then
      log "USB ${tree:-empty}"; previous=$tree
    fi
    sleep 0.15
  done
}
override_id=
watch_pid=
finish() {
  result=$?
  trap - EXIT HUP INT TERM
  if [ -n "$override_id" ]; then
    if [ "$(cv10_id)" = "$override_id" ]; then
      cmd display power-reset "$override_id" || result=1
      log "cleanup power-reset id=$override_id powerMode=$(power_mode)"
    else
      log 'original display disappeared during override'
    fi
  fi
  if [ -n "$watch_pid" ]; then
    kill "$watch_pid" 2>/dev/null
    wait "$watch_pid" 2>/dev/null
  fi
  exit "$result"
}
trap finish EXIT
trap 'exit 130' HUP INT TERM
old=$(cv10_id) || old=
log "READY mode=$mode"
watch_usb &
watch_pid=$!
end=$(( $(date +%s) + 180 ))
if [ -n "$old" ]; then
  log "waiting for currently attached CV10 id=$old to be unplugged"
  while cv10_id >/dev/null; do
    [ "$(date +%s)" -lt "$end" ] || { log 'timed out waiting for unplug'; exit 3; }
    sleep 0.15
  done
fi
log 'waiting for a new external display'
while ! new=$(cv10_id); do
  [ "$(date +%s)" -lt "$end" ] || { log 'timed out waiting for attach'; exit 3; }
  sleep 0.08
done
log "attached HUAWEIAV03 id=$new"
if [ "$mode" = delay ]; then
  [ "$(cv10_id)" = "$new" ] || { log 'target changed before power-off'; exit 4; }
  override_id=$new
  cmd display power-off "$new" || exit 4
fi
start=$(date +%s%3N)
last=
while [ $(( $(date +%s%3N) - start )) -lt 12000 ]; do
  state=$(power_mode)
  if [ "$state" != "$last" ]; then log "powerMode=$state"; last=$state; fi
  sleep 0.20
done
if [ "$mode" = delay ]; then
  [ "$(cv10_id)" = "$new" ] || { log 'target changed during delay'; exit 4; }
  cmd display power-reset "$new" || exit 4
  log "released id=$new powerMode=$(power_mode)"
fi
sleep 12
state=$(power_mode)
log "observation ended powerMode=$state"
if [ "$mode" = delay ]; then
  if [ "$state" = ON ]; then
    override_id=
  else
    log 'could not confirm ON after reset'
    exit 4
  fi
fi
