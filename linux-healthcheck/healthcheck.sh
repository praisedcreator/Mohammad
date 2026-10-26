#!/usr/bin/env bash
# Read-only Linux health summary. Exit 0=healthy, 1=warning, 2=invalid input.
set -euo pipefail
export LC_ALL=C

fixture_dir=''
disk_path='/'
fail() { printf 'healthcheck: %s\n' "$1" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --fixture-dir) (($# >= 2)) || fail 'missing fixture directory'; fixture_dir=$2; shift 2 ;;
    --disk-path) (($# >= 2)) || fail 'missing disk path'; disk_path=$2; shift 2 ;;
    --help) printf '%s\n' 'Usage: bash healthcheck.sh [--disk-path PATH] [--fixture-dir DIR]'; exit 0 ;;
    *) fail 'unknown argument' ;;
  esac
done

if [[ -n "$fixture_dir" ]]; then
  for filename in meminfo loadavg disk_percent cpu_count; do
    [[ -r "$fixture_dir/$filename" ]] || fail "missing fixture: $filename"
  done
  meminfo=$(cat -- "$fixture_dir/meminfo")
  load1=$(awk 'NR==1 {print $1}' "$fixture_dir/loadavg")
  disk=$(cat -- "$fixture_dir/disk_percent")
  cpus=$(cat -- "$fixture_dir/cpu_count")
  mode='fixture'
else
  [[ $(uname -s) == 'Linux' ]] || fail 'live mode requires Linux; use fixtures on other platforms'
  [[ -r /proc/meminfo && -r /proc/loadavg ]] || fail 'Linux proc metrics are unavailable'
  meminfo=$(cat /proc/meminfo)
  load1=$(awk 'NR==1 {print $1}' /proc/loadavg)
  disk=$(df -Pk -- "$disk_path" | awk 'NR==2 {gsub(/%/,"",$5); print $5}') || fail 'disk metric unavailable'
  cpus=$(getconf _NPROCESSORS_ONLN) || fail 'CPU count unavailable'
  mode='live_read_only'
fi

total=$(printf '%s\n' "$meminfo" | awk '$1=="MemTotal:" {print $2}')
available=$(printf '%s\n' "$meminfo" | awk '$1=="MemAvailable:" {print $2}')
[[ "$total" =~ ^[0-9]+$ && "$available" =~ ^[0-9]+$ && "$cpus" =~ ^[0-9]+$ ]] || fail 'invalid memory or CPU metric'
[[ "$load1" =~ ^[0-9]+([.][0-9]+)?$ && "$disk" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail 'invalid load or disk metric'
awk -v t="$total" -v a="$available" -v c="$cpus" -v d="$disk" 'BEGIN {exit !(t>0 && a<=t && c>0 && d>=0 && d<=100)}' || fail 'metric outside valid range'
memory=$(awk -v t="$total" -v a="$available" 'BEGIN {printf "%.2f",100*(t-a)/t}')
load_per_cpu=$(awk -v l="$load1" -v c="$cpus" 'BEGIN {printf "%.2f",l/c}')
# Compare unrounded values so presentation rounding cannot trigger an alert.
status='healthy'
exit_code=0
if awk -v t="$total" -v a="$available" -v d="$disk" -v l="$load1" -v c="$cpus" 'BEGIN {exit !(100*(t-a)/t >= 85 || d >= 85 || l/c >= 1.5)}'; then
  status='warning'
  exit_code=1
fi
printf '{"status":"%s","mode":"%s","memory_used_percent":%s,"disk_used_percent":%s,"load_per_cpu":%s}\n' \
  "$status" "$mode" "$memory" "$disk" "$load_per_cpu"
exit "$exit_code"
