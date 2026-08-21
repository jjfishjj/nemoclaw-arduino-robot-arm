# Deployment guide

## Local SQLite demo

Run Mosquitto, then `npm start`. SQLite is selected when `DATABASE_URL` is absent.

## PostgreSQL demo

`docker compose up --build` starts PostgreSQL, Mosquitto and the edge service. The
service applies the idempotent migration and uses a bounded connection pool.

Production changes: use a secret-managed password, TLS for PostgreSQL/MQTT, backups,
PgBouncer transaction mode, health monitoring, and a scheduled retention call.

The included `docker-compose.secure.yml` implements file-backed secrets, mutual TLS
for MQTT, authenticated APIs and readiness checks. It intentionally ships without
certificates or credentials. Review `secrets/README.md`, then launch both Compose files.

For an internet-facing host, set `DEPLOY_DOMAIN` and `ACME_EMAIL`, point DNS at the
host, and add `docker-compose.production.yml`. Caddy terminates HTTPS and persists
ACME state; the edge service is no longer exposed directly. The production overlay
also applies read-only/no-new-privileges restrictions. Validate DNS and ports 80/443
before launch; a placeholder domain must never be treated as a completed deployment.

Run retention as a scheduled one-shot workload:

```sh
docker compose -f docker-compose.yml -f docker-compose.secure.yml \
  -f docker-compose.production.yml --profile maintenance run --rm retention
```

Each successful PostgreSQL run is recorded in `retention_runs` and emits a JSON
evidence file. Schedule it daily with the host's timer service and alert on non-zero exit.
Use `python scripts/health_monitor.py --url https://$DEPLOY_DOMAIN/health/ready`
as a monitoring probe; its JSON output is suitable for log ingestion and its exit code
is suitable for uptime or scheduler alerts.

## Backup and recovery

`scripts/backup.py` uses SQLite's online backup API or `pg_dump --format=custom`.
Exercise recovery periodically: restore PostgreSQL with `pg_restore --clean --if-exists`
into a non-production database, or open the SQLite copy and run `pragma integrity_check`.
Keep encrypted backups outside the host and document retention separately from telemetry.

## Jetson

Create a fresh virtual environment on the Jetson, install dependencies compatible
with its JetPack image, then run `jetson/validate_on_jetson.sh [NVP_MODEL_MODE]`.
The optional mode argument changes device power mode through `sudo nvpmodel`; omit it
to preserve and merely record the current mode.
For SSH-key based automation, set `JETSON_HOST` and run `scripts/run_jetson_remote.sh`.

## ESP32

Set Wi-Fi/MQTT values in `firmware/include/config.h`, compile with PlatformIO and
upload over USB. Validate sensor addresses and calibration on physical hardware.
