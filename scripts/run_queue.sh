#!/usr/bin/env bash
# Pull runs from a queue made by scripts/make_queue.py until it is empty. Each "cell" is one checkout of this repo
# with its own .env (inbox) and Circle session (HOME), so several cells can share a queue and run in parallel:
#   scripts/run_queue.sh <queue_dir> <cell_name> [circle_home]
# Each run first resets the policy to 0.01 USDC of room (scripts/headroom.py); a run whose reset fails goes back
# to the queue.
set -u
Q=$(cd "$1" && pwd); CELL=$2; [ -n "${3:-}" ] && export HOME=$3
cd "$(dirname "$0")/.."
export CIRCLE_ACCEPT_TERMS=1
PY=${PYTHON:-python}; LOGDIR=logs; mkdir -p "$LOGDIR"
echo "start $CELL $(date -u +%FT%TZ)"
while true; do
  f=$(ls "$Q/pending" 2>/dev/null | sort | head -1); [ -z "$f" ] && break
  mv "$Q/pending/$f" "$Q/claimed/${CELL}__$f" 2>/dev/null || continue
  touch "$Q/claimed/${CELL}__$f"
  scen=$(echo "$f" | awk -F'__' '{print $2}'); m=$(echo "$f" | awk -F'__' '{print $3}' | sed 's#~#:#; s#~#/#')
  echo "### [$CELL] $f | $(date -u +%H:%M:%S)"
  ok=0; for _ in 1 2 3; do timeout 600 $PY scripts/headroom.py > "$LOGDIR/headroom_$CELL.txt" 2>&1 && { ok=1; break; }; sleep 30; done
  if [ $ok -ne 1 ]; then
    echo "  [$CELL] policy reset failed, requeued: $(tail -1 "$LOGDIR/headroom_$CELL.txt")"
    mv "$Q/claimed/${CELL}__$f" "$Q/pending/$f"; sleep 300; continue
  fi
  timeout 1500 $PY run.py --scenario "$scen" --net mainnet --agent "$m" --max-steps 40 > "$LOGDIR/$f.log" 2>&1; rc=$?
  r=$(ls -t results/lc3_${scen}_$(echo "$m" | sed 's#[:/]#-#g')_*.json 2>/dev/null | head -1)
  if [ -n "$r" ] && [ "$r" -nt "$Q/claimed/${CELL}__$f" ]; then
    echo "  -> [$CELL] $(basename "$r") (rc $rc)"; mv "$Q/claimed/${CELL}__$f" "$Q/done/$f"
  else
    echo "  [$CELL] no result (rc $rc): $(tail -2 "$LOGDIR/$f.log" | tr '\n' ' ' | cut -c1-200)"; mv "$Q/claimed/${CELL}__$f" "$Q/done/FAILED__$f"
  fi
done
$PY scripts/headroom.py > /dev/null 2>&1
echo "done $CELL $(date -u +%FT%TZ)"
