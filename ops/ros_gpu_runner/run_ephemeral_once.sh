#!/usr/bin/env bash
set -euo pipefail

: "${EPHEMERAL_LOG_DIR:?Set EPHEMERAL_LOG_DIR to an externally persisted log mount}"
teardown_hook="${EPHEMERAL_TEARDOWN_HOOK:-/usr/local/sbin/destroy-ephemeral-runner}"
if [[ ! -x "$teardown_hook" ]]; then
  echo "Missing root-owned executable teardown hook: $teardown_hook" >&2
  exit 2
fi
if [[ "$teardown_hook" != /* ]]; then
  echo "EPHEMERAL_TEARDOWN_HOOK must be an absolute path" >&2
  exit 2
fi

export EPHEMERAL_RUNNER=1
export RUNNER_LABELS="${RUNNER_LABELS:-ros2-jazzy,gpu,gazebo,ephemeral}"
runner_root="${RUNNER_ROOT:-$HOME/actions-runner}"
cleanup_started=0

cleanup() {
  status=$?
  if [[ "$cleanup_started" -eq 1 ]]; then
    return
  fi
  cleanup_started=1
  mkdir -p "$EPHEMERAL_LOG_DIR"
  if [[ -d "$runner_root/_diag" ]]; then
    cp -a "$runner_root/_diag/." "$EPHEMERAL_LOG_DIR/" || true
  fi
  printf '%s\n' "$status" >"$EPHEMERAL_LOG_DIR/runner_exit_status" || true
  sync
  sudo "$teardown_hook" "$status" || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$script_dir/register_runner.sh"
cd "$runner_root"
set +e
./run.sh
runner_status=$?
set -e
exit "$runner_status"
