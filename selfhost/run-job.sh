#!/usr/bin/env bash
# Run one of the site's data jobs at home — the same steps the GitHub Actions workflows ran.
#   selfhost/run-job.sh stocks|earnings|news|deals|radio|monitor|all
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
[ -f "$HERE/config.env" ] && set -a && . "$HERE/config.env" && set +a
export TOOLS_DATA="${TOOLS_DATA:-$ROOT/.local-data}" LOCAL_ISSUES=1 OWNER="${OWNER:-boliunew}" PYTHONUNBUFFERED=1
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
mkdir -p "$TOOLS_DATA/logs"
cd "$ROOT"

job="${1:-}"
if [ "$job" = "all" ]; then
  for j in stocks earnings news deals monitor radio; do "$0" "$j"; done
  exit 0
fi

steps() {
  case "$1" in
    stocks)   printf '%s\n' "stocks/scan.py" "stocks/alerts.py check" ;;
    earnings) printf '%s\n' "earnings/build.py" ;;
    news)     printf '%s\n' "news/build.py" "news/contexts.py" "news/articles.py" "card/today.py" ;;
    deals)    printf '%s\n' "deals/build.py" ;;
    radio)    printf '%s\n' "radio/build.py" ;;
    monitor)  printf '%s\n' "monitor/check.py" ;;
    *) return 1 ;;
  esac
}
list="$(steps "$job")" || { echo "usage: $0 stocks|earnings|news|deals|radio|monitor|all"; exit 2; }

LOG="$TOOLS_DATA/logs/$job.log"
# keep logs small: last ~2000 lines
[ -f "$LOG" ] && tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exec 9>"$TOOLS_DATA/logs/$job.lock"
if ! flock -n 9; then echo "$(date '+%F %T') $job already running, skipped" >> "$LOG"; exit 0; fi

status=0
{
  echo "===== $(date '+%F %T') $job"
  while IFS= read -r step; do
    echo "--- python $step"
    case "$job" in
      radio)   RADIO_NO_UPLOAD=1 LOCAL_KV="$TOOLS_DATA/kv" "$PY" $step < /dev/null || status=$? ;;
      monitor) EVENT_NAME=schedule "$PY" $step < /dev/null || status=$? ;;
      *)       "$PY" $step < /dev/null || status=$? ;;
    esac
  done <<< "$list"
  echo "===== $(date '+%F %T') $job done (exit $status)"
} >> "$LOG" 2>&1
if [ "$status" != 0 ] && [ -n "${NTFY_URL:-}" ]; then
  curl -s -m 10 -H "Title: tools job failed: $job" -H "Tags: warning" -d "$(tail -n 15 "$LOG")" "$NTFY_URL" > /dev/null || true
fi
exit "$status"
