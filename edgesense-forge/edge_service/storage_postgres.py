from __future__ import annotations

import json
from pathlib import Path

from .schemas import BenchmarkResult, EdgeEvent


class PostgresEventStore:
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 8) -> None:
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError("PostgreSQL selected but psycopg dependencies are not installed") from exc
        self.pool = ConnectionPool(database_url, min_size=min_size, max_size=max_size,
                                   kwargs={"row_factory": dict_row}, open=True)
        migration = Path(__file__).resolve().parent.parent / "migrations/postgres/001_initial.sql"
        with self.pool.connection() as connection:
            connection.execute(migration.read_text())

    def save_event(self, event: EdgeEvent, create_alert: bool = True) -> int:
        row = event.model_dump(mode="json"); telemetry = row["telemetry"]; inference = row["inference"]
        with self.pool.connection() as connection:
            result = connection.execute(
                """insert into telemetry (device_id,measured_at,received_at,temperature_c,accel_rms_g,
                anomaly_score,is_anomaly,reason_codes,engine,model_version,latency_ms)
                values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) returning id""",
                (telemetry["device_id"], telemetry["ts"], row["received_at"], telemetry["temperature_c"],
                 telemetry["accel_rms_g"], inference["score"], inference["is_anomaly"],
                 json.dumps(inference["reason_codes"]), inference["engine"], inference["model_version"],
                 inference["latency_ms"]),
            ).fetchone()
            telemetry_id = result["id"]
            if inference["is_anomaly"] and create_alert:
                connection.execute(
                    "insert into alerts(telemetry_id,created_at,updated_at) values(%s,%s,%s) on conflict do nothing",
                    (telemetry_id, row["received_at"], row["received_at"]),
                )
            return telemetry_id

    def save_benchmark(self, result: BenchmarkResult) -> int:
        row = result.model_dump(mode="json"); columns = list(row)
        with self.pool.connection() as connection:
            saved = connection.execute(
                f"insert into benchmark_runs ({','.join(columns)}) values ({','.join('%s' for _ in columns)}) returning id",
                tuple(row[column] for column in columns),
            ).fetchone()
            return saved["id"]

    def _telemetry(self, anomaly_only: bool, device_id: str | None, limit: int) -> list[dict]:
        clauses = ["is_anomaly" if anomaly_only else "true"]; params: list[object] = []
        if device_id: clauses.append("device_id=%s"); params.append(device_id)
        params.append(limit)
        with self.pool.connection() as connection:
            return list(connection.execute(
                f"select * from telemetry where {' and '.join(clauses)} order by measured_at desc,id desc limit %s", params
            ).fetchall())

    def history(self, device_id=None, limit=120): return self._telemetry(False, device_id, limit)
    def anomalies(self, device_id=None, limit=50): return self._telemetry(True, device_id, limit)

    def benchmarks(self, limit=50):
        with self.pool.connection() as connection:
            return list(connection.execute("select * from benchmark_runs order by measured_at desc,id desc limit %s", (limit,)).fetchall())

    def summary(self):
        with self.pool.connection() as connection:
            row = connection.execute("select count(*) samples,count(*) filter(where is_anomaly) anomalies,count(distinct device_id) devices,max(measured_at) latest_at from telemetry").fetchone()
        return row

    def alert_page(self, status=None, cursor=None, limit=30):
        clauses=["true"]; params=[]
        if status: clauses.append("a.status=%s"); params.append(status)
        if cursor: clauses.append("a.id<%s"); params.append(cursor)
        params.append(limit+1)
        with self.pool.connection() as connection:
            rows=list(connection.execute(f"select a.id alert_id,a.status,a.note,a.actor,a.created_at,a.updated_at,t.* from alerts a join telemetry t on t.id=a.telemetry_id where {' and '.join(clauses)} order by a.id desc limit %s",params).fetchall())
        more=len(rows)>limit; rows=rows[:limit]
        return {"items":rows,"next_cursor":rows[-1]["alert_id"] if more else None}

    def update_alert(self, alert_id,status,note,actor,updated_at):
        with self.pool.connection() as connection:
            return connection.execute("update alerts set status=%s,note=%s,actor=%s,updated_at=%s where id=%s returning *",(status,note,actor,updated_at,alert_id)).fetchone()

    def get_rule(self, device_id):
        with self.pool.connection() as connection: row=connection.execute("select * from alert_rules where device_id=%s",(device_id,)).fetchone()
        return row or {"device_id":device_id,"enabled":True,"anomaly_threshold":0.7,"temperature_threshold_c":70.0,"retention_days":30,"updated_at":None}

    def upsert_rule(self,device_id,enabled,anomaly_threshold,temperature_threshold_c,retention_days,updated_at):
        with self.pool.connection() as connection:
            return connection.execute("""insert into alert_rules values(%s,%s,%s,%s,%s,%s) on conflict(device_id) do update set enabled=excluded.enabled,anomaly_threshold=excluded.anomaly_threshold,temperature_threshold_c=excluded.temperature_threshold_c,retention_days=excluded.retention_days,updated_at=excluded.updated_at returning *""",(device_id,enabled,anomaly_threshold,temperature_threshold_c,retention_days,updated_at)).fetchone()

    def purge_before(self,cutoff):
        with self.pool.connection() as connection:
            deleted=connection.execute("delete from telemetry where measured_at<%s",(cutoff,)).rowcount
            benchmarks_deleted=connection.execute("delete from benchmark_runs where measured_at<%s",(cutoff,)).rowcount
            connection.execute(
                "insert into retention_runs(cutoff,telemetry_deleted,benchmark_runs_deleted) values(%s,%s,%s)",
                (cutoff, deleted, benchmarks_deleted),
            )
            return deleted

    def ping(self):
        with self.pool.connection(timeout=3) as connection:
            return connection.execute("select 1 ok").fetchone()["ok"] == 1
