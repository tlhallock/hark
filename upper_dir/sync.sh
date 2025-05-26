#!/bin/bash

SRC_DIR="/home/thallock/recordings"
DST_DIR="thallock@10.0.0.129:/work/projects/tracker/mic/auto-sync"
KEY="/home/thallock/.ssh/id_ed25519"

# Find all .opus files not currently open by any process
find "$SRC_DIR" -name '*.opus' | while read file; do
    if ! lsof "$file" >/dev/null; then
        scp -i "$KEY" "$file" "$DST_DIR" && rm "$file"
    fi
done

