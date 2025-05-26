#!/bin/bash
scp -i pi_key bin/sync.sh thallock@10.0.0.205:/home/thallock/bin
scp -i pi_key bin/record.sh thallock@10.0.0.205:/home/thallock/bin
