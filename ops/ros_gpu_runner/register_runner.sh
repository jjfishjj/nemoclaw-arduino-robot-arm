#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_URL:?Set GITHUB_URL to the repository or organization URL}"
: "${RUNNER_TOKEN:?Set RUNNER_TOKEN to GitHub's short-lived registration token}"
: "${RUNNER_VERSION:?Set RUNNER_VERSION to the version shown by GitHub, for example 2.3xx.x}"
: "${RUNNER_SHA256:?Set RUNNER_SHA256 to the Linux x64 checksum shown by GitHub}"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not register the runner as root." >&2
  exit 2
fi
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "This registration script supports Linux x86_64 only." >&2
  exit 2
fi

runner_root="${RUNNER_ROOT:-$HOME/actions-runner}"
runner_name="${RUNNER_NAME:-$(hostname)-ros-gpu}"
runner_labels="${RUNNER_LABELS:-ros2-jazzy,gpu,gazebo}"
archive="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
download_url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${archive}"

mkdir -p "$runner_root"
if [[ -e "$runner_root/.runner" ]]; then
  echo "$runner_root is already configured; refusing to replace it implicitly." >&2
  exit 1
fi
curl -fL --retry 3 -o "$runner_root/$archive" "$download_url"
printf '%s  %s\n' "$RUNNER_SHA256" "$runner_root/$archive" | sha256sum --check --strict
tar -xzf "$runner_root/$archive" -C "$runner_root"
rm "$runner_root/$archive"

args=(
  --url "$GITHUB_URL"
  --token "$RUNNER_TOKEN"
  --name "$runner_name"
  --labels "$runner_labels"
  --work "_work"
  --unattended
)
if [[ -n "${RUNNER_GROUP:-}" ]]; then
  args+=(--runnergroup "$RUNNER_GROUP")
fi
if [[ "${EPHEMERAL_RUNNER:-0}" == "1" ]]; then
  args+=(--ephemeral --disableupdate)
fi

cd "$runner_root"
./config.sh "${args[@]}"

if [[ "${EPHEMERAL_RUNNER:-0}" == "1" ]]; then
  echo "Ephemeral runner registered. Start it with: cd $runner_root && ./run.sh"
else
  sudo ./svc.sh install "$(id -un)"
  sudo ./svc.sh start
  sudo ./svc.sh status
fi

unset RUNNER_TOKEN
echo "Runner registered as $runner_name with custom labels: $runner_labels"
