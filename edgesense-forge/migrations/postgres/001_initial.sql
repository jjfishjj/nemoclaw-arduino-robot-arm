create table if not exists telemetry (
  id bigint generated always as identity primary key,
  device_id text not null,
  measured_at timestamptz not null,
  received_at timestamptz not null,
  temperature_c double precision not null check (temperature_c between -40 and 125),
  accel_rms_g double precision not null check (accel_rms_g between 0 and 16),
  anomaly_score double precision not null check (anomaly_score between 0 and 1),
  is_anomaly boolean not null,
  reason_codes jsonb not null,
  engine text not null,
  model_version text not null,
  latency_ms double precision not null check (latency_ms >= 0)
);
create index if not exists telemetry_device_time_idx on telemetry(device_id, measured_at desc, id desc);
create index if not exists telemetry_anomaly_time_idx on telemetry(measured_at desc, id desc) where is_anomaly;

create table if not exists benchmark_runs (
  id bigint generated always as identity primary key,
  engine text not null, model_version text not null, runtime_version text not null,
  device text not null, host_arch text not null, warmup_runs integer not null,
  measured_runs integer not null, mean_ms double precision not null,
  p50_ms double precision not null, p95_ms double precision not null,
  min_ms double precision not null, max_ms double precision not null,
  measured_at timestamptz not null, evidence text not null check (evidence = 'measured')
);

create table if not exists alerts (
  id bigint generated always as identity primary key,
  telemetry_id bigint not null unique references telemetry(id) on delete cascade,
  status text not null default 'open' check (status in ('open','acknowledged','resolved')),
  note text not null default '', actor text not null default 'system',
  created_at timestamptz not null, updated_at timestamptz not null
);
create index if not exists alerts_active_idx on alerts(updated_at desc, id desc) where status != 'resolved';

create table if not exists alert_rules (
  device_id text primary key, enabled boolean not null default true,
  anomaly_threshold double precision not null check (anomaly_threshold between 0.1 and 0.99),
  temperature_threshold_c double precision not null check (temperature_threshold_c between 20 and 120),
  retention_days integer not null default 30 check (retention_days between 1 and 3650),
  updated_at timestamptz not null
);
