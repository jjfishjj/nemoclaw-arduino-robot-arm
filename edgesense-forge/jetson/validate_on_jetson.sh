#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
report_dir="${project_dir}/data/jetson-validation-$(date -u +%Y%m%dT%H%M%SZ)"
power_mode="${1:-}"

if [[ ! -f /etc/nv_tegra_release ]]; then
  echo "ERROR: NVIDIA Jetson was not detected." >&2
  exit 2
fi
if [[ -n "${power_mode}" ]]; then
  echo "Setting nvpmodel mode ${power_mode}; sudo approval may be requested."
  sudo nvpmodel -m "${power_mode}"
fi
mkdir -p "${report_dir}"
nvpmodel -q > "${report_dir}/power-mode.txt" 2>&1
if command -v jetson_clocks >/dev/null 2>&1; then
  jetson_clocks --show > "${report_dir}/clocks.txt" 2>&1 || true
fi
cat /etc/nv_tegra_release > "${report_dir}/jetson-release.txt"
uname -a > "${report_dir}/uname.txt"
trtexec --version > "${report_dir}/tensorrt-version.txt" 2>&1 || true

tegrastats --interval 500 --logfile "${report_dir}/tegrastats.log" &
tegrastats_pid=$!
cleanup() { kill "${tegrastats_pid}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

"${project_dir}/jetson/build_engine.sh" | tee "${report_dir}/engine-build.log"
"${project_dir}/.venv/bin/python" "${project_dir}/jetson/compare_engines.py" \
  --warmup 20 --iterations 200 --output "${report_dir}/comparison.json" \
  | tee "${report_dir}/comparison.stdout.json"
cleanup
trap - EXIT INT TERM
"${project_dir}/.venv/bin/python" "${project_dir}/jetson/render_report.py" "${report_dir}"
echo "Jetson validation package: ${report_dir}"
