#!/bin/bash

mkdir -p ~/recordings
while true; do
  ffmpeg -f alsa -ac 1 -i hw:2 \
    -c:a libopus \
    -f segment \
    -segment_time 7200 \
    -strftime 1 \
    -reset_timestamps 1 \
    /home/thallock/recordings/%Y-%m-%d_%H-%M-%S.opus
done

