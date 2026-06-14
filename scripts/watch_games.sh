#!/bin/bash
# Simple game watcher - shows new replays as they appear

REPLAY_DIR="saved_replays/real_replays_d3"

echo "=========================================="
echo "Watching for games in: $REPLAY_DIR"
echo "=========================================="

count=0
while true; do
    if [ -d "$REPLAY_DIR" ]; then
        files=$(ls -1t "$REPLAY_DIR"/*.pkl 2>/dev/null | wc -l)
        if [ $files -gt $count ]; then
            count=$files
            echo ""
            echo "[$(date '+%H:%M:%S')] Games found: $count"
            ls -lhS "$REPLAY_DIR"/*.pkl 2>/dev/null | head -5 | awk '{print "  " $9 " (" $5 ")"}'
        fi
    else
        echo "Waiting for $REPLAY_DIR to be created..."
    fi
    sleep 3
done
