# Self-hosted ROS 2 / NVIDIA GPU runner

This bundle provisions trusted Ubuntu 24.04 x86_64 images for native ROS 2
Jazzy, Gazebo Harmonic, MCAP, and NVIDIA GPU benchmark jobs. The recommended
production mode is a fresh ephemeral VM per job. Docker and NVIDIA Container
Toolkit are optional; the rover workflow itself runs on the host.

## Host baseline

- Ubuntu 24.04 x86_64, at least 16 GB RAM and 50 GiB free workspace storage
- NVIDIA GPU with a working host driver (`nvidia-smi` must succeed)
- A dedicated unprivileged account, for example `gha-runner`
- A private repository, or an organization runner group restricted to trusted
  private repositories
- A saved benchmark map readable at `/opt/rover/maps/rover_map.yaml`, or a
  repository variable named `ROVER_BENCHMARK_MAP` pointing to another absolute
  path on the runner

The workflow intentionally has no `pull_request` or `push` trigger. A persistent
self-hosted runner retains state and network access, so it must not execute code
from untrusted forks.

## 1. Prepare the dedicated account

Run once from an administrator account:

```bash
sudo adduser --disabled-password --gecos "" gha-runner
sudo usermod -aG docker gha-runner  # only when Docker is required
sudo install -d -o gha-runner -g gha-runner /opt/rover/maps
sudo install -o gha-runner -g gha-runner rover_map.yaml /opt/rover/maps/rover_map.yaml
```

Log in as `gha-runner`, clone this repository, then install the pre-declared
host dependencies. The script deliberately refuses to install an NVIDIA driver;
driver selection and reboot belong to host administration.

```bash
cd /path/to/repository
ops/ros_gpu_runner/install_host_dependencies.sh
ops/ros_gpu_runner/preflight.sh
```

Set `INSTALL_NVIDIA_CONTAINER_TOOLKIT=0` when Docker GPU jobs are not needed.

## 2. Recommended: one-job ephemeral VM

The lifecycle is deliberately provider-neutral:

```text
workflow_job queued webhook
  -> trusted provisioner clones the sealed GPU image
  -> injects a registration token valid for one hour
  -> run_ephemeral_once.sh registers with --ephemeral --disableupdate
  -> one benchmark job runs
  -> runner diagnostics are copied to external storage
  -> root-owned teardown hook powers off the VM
  -> provider terminates the VM and delete-on-termination disks
```

Build the image by running `install_host_dependencies.sh`, installing a reviewed
copy of `destroy_ephemeral_runner.example.sh` at
`/usr/local/sbin/destroy-ephemeral-runner`, writing an immutable image build ID
such as `rover-gpu-2026-08-17.1` to `/etc/rover-gpu-image-id`, and placing the repository at
`/opt/rover-repo`. `cloud-init.example.yaml` shows the boot service contract.
The provisioner must create the short-lived registration token through a GitHub
App with repository Administration write permission; never bake it into the
image or cloud-init user data.

Required runtime variables are the four registration values below plus an
externally persisted diagnostic mount:

```bash
export EPHEMERAL_LOG_DIR=/mnt/runner-diagnostics/$RUNNER_NAME
export EPHEMERAL_RUNNER=1
ops/ros_gpu_runner/run_ephemeral_once.sh
```

The teardown hook must be root-owned and non-writable by `gha-runner`. Configure
the VM platform so guest shutdown means **terminate**, and all scratch disks are
deleted. Merely registering with `--ephemeral` deregisters the GitHub runner but
does not destroy the VM by itself.

The workflow rejects a missing/malformed image ID or a VM boot age above four
hours, even when the runner carries the `ephemeral` label. The example systemd
unit powers off after success, failure, or a three-hour runtime limit. The cloud
provider must still map shutdown to termination and enforce a separate maximum
instance lifetime for failures that happen before the guest service starts.

For Kubernetes fleets, use GitHub Actions Runner Controller rather than this
single-VM bootstrap contract. For non-Kubernetes VM fleets, trigger provisioning
from the `workflow_job` webhook only when all labels include
`self-hosted,ros2-jazzy,gpu,gazebo,ephemeral`.

## 3. Persistent fallback registration

In GitHub, open **Settings > Actions > Runners > New self-hosted runner** and
select Linux x64. Copy its current runner version, SHA-256 checksum, repository
URL, and short-lived registration token into a local shell. Do not populate or
commit `runner.env.example`.

```bash
export GITHUB_URL=https://github.com/OWNER/REPOSITORY
export RUNNER_TOKEN='short-lived-value-from-github'
export RUNNER_VERSION='version-shown-by-github'
export RUNNER_SHA256='linux-x64-sha256-shown-by-github'
export RUNNER_NAME=rover-gpu-01
ops/ros_gpu_runner/register_runner.sh
unset RUNNER_TOKEN
```

The script verifies the official archive before extraction, adds the custom
labels `ros2-jazzy,gpu,gazebo`, and installs a systemd service. GitHub supplies
the default `self-hosted,linux,x64` labels. It refuses to overwrite an existing
registration.

Persistent registration is retained only for development and recovery. It does
not match the production workflow because that workflow additionally requires
the `ephemeral` label.

## 4. Run, monitor, and inspect evidence

Set the optional repository variable `ROVER_BENCHMARK_MAP`, then open
**Actions > ROS 2 Rover GPU Benchmark > Run workflow**. Weekday scheduled runs
start at 18:17 UTC (02:17 Asia/Taipei on the following day). Jobs are serialized
so two Gazebo processes cannot share the GPU simultaneously.

Each run builds the workspace, starts deterministic randomized Gazebo trials,
enforces the versioned KPI thresholds, and uploads JSON, standalone HTML, SDF,
logs, and MCAP for 14 days. `compression-level: 0` avoids wasting runner CPU on
already-compressed MCAP data.

Every trial also contains `trial_N_gpu.csv` with one-second samples of GPU
utilization, framebuffer memory, temperature, power draw, and workspace disk
capacity. Trial JSON records simulated-time real-time factor, observed global
planning latency, peak VRAM, peak temperature, minimum free disk, and MCAP size.
`runner_metrics.json` records the ephemeral identity and approximate job queue
time from the end of the queue-marker job until the GPU runner starts.

The versioned gate currently requires RTF >= 0.75, mean plan latency <= 750 ms,
peak VRAM <= 12000 MiB, and each MCAP <= 2048 MiB. Tune these limits only from a
reviewed baseline collected on the target GPU image; hardware changes should use
a separate baseline rather than silently widening the same limits.

## Operations and security

- Never grant the runner account general passwordless sudo. Provision packages
  outside jobs; CI uses `rosdep check`, not `rosdep install`.
- Restrict organization runner groups to the intended repositories and trusted
  workflows. Keep workflow `permissions` read-only unless a specific job needs
  more.
- Keep maps non-secret. GitHub artifact contents are visible to users who can
  read the workflow run.
- Patch Ubuntu, the NVIDIA driver, ROS packages, and the Actions runner on a
  maintenance schedule. The Actions runner service auto-updates by default.
- Monitor disk usage: MCAP and colcon build trees persist on a persistent
  runner even though uploaded artifacts expire.
- Treat a persistent runner compromise as a host compromise: stop the service,
  remove the runner in GitHub, rotate reachable credentials, and rebuild the
  machine from a trusted image.
