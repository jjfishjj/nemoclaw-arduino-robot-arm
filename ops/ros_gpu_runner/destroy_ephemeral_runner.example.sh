#!/usr/bin/env bash
set -euo pipefail

# Install a reviewed provider-specific version of this file as:
#   /usr/local/sbin/destroy-ephemeral-runner
# owned by root and not writable by the runner account. Configure the VM provider
# to TERMINATE (not merely stop) the instance when the guest powers off, and make
# all scratch disks delete-on-termination.

runner_exit_status="${1:-1}"
logger -t ephemeral-gpu-runner "one-shot runner exited with status $runner_exit_status; powering off"
/sbin/shutdown -h now
