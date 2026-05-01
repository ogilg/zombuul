#!/usr/bin/env bash
# safe_rsync.sh — thin rsync wrapper that always emits a parseable summary.
#
# Usage:  safe_rsync.sh <rsync args...>
#
# Forces `--stats`, captures output, and prints a final line:
#     [safe_rsync] EXIT=<code> FILES=<n>
# regardless of whether the caller pipes through tail/head. Lets agents tell
# at a glance whether the transfer actually moved anything — bare `rsync`
# calls have been silently swallowed by `| tail -5` and exit-code checks
# while a missing source dir or malformed args produced 0 files.

set -uo pipefail

if [ $# -eq 0 ]; then
    echo "[safe_rsync] usage: safe_rsync.sh <rsync args...>" >&2
    exit 64
fi

out=$(mktemp -t safe_rsync.XXXXXX)
trap 'rm -f "$out"' EXIT

rsync --stats "$@" 2>&1 | tee "$out"
rc=${PIPESTATUS[0]}

n=$(grep -m1 -E "^Number of (regular )?files transferred:" "$out" | sed 's/[^0-9]//g')
n=${n:-?}

echo "[safe_rsync] EXIT=$rc FILES=$n"
exit "$rc"
