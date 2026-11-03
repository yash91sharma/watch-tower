#!/bin/sh
# Test app. It writes one log line each second. Env MODE: "normal" or "json".
#   Unhealthy:  docker exec <name> rm /tmp/ok        (back: touch /tmp/ok)
#   Crash K times (with restart: on-failure):
#               docker exec <name> sh -c 'echo K > /tmp/crash'
#               The app exits now and on the next K-1 starts, then runs.

trap 'exit 0' TERM INT

crash_if_asked() {
  if [ -f /tmp/crash ]; then
    left=$(cat /tmp/crash)
    if [ "$left" -gt 0 ] 2>/dev/null; then
      echo $((left - 1)) > /tmp/crash
      echo "crash, $((left - 1)) more" >&2
      exit 1
    fi
  fi
}

crash_if_asked
touch /tmp/ok
n=0
while true; do
  n=$((n + 1))
  if [ "$MODE" = "json" ]; then
    echo "{\"level\":\"info\",\"n\":$n,\"msg\":\"tick\"}"
    echo "error line $n" >&2
  else
    echo "tick $n"
  fi
  sleep 1
  crash_if_asked
done
