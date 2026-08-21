from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from .schemas import BenchmarkResult, EdgeEvent


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    measured_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    temperature_c REAL NOT NULL,
                    accel_rms_g REAL NOT NULL,
                    anomaly_score REAL NOT NULL,
                    is_anomaly INTEGER NOT NULL,
                    reason_codes TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    latency_ms REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
                    ON telemetry(device_id, measured_at DESC);
                CREATE INDEX IF NOT EXISTS idx_telemetry_anomaly_time
                    ON telemetry(is_anomaly, measured_at DESC);
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    engine TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    runtime_version TEXT NOT NULL,
                    device TEXT NOT NULL,
                    host_arch TEXT NOT NULL,
                    warmup_runs INTEGER NOT NULL,
                    measured_runs INTEGER NOT NULL,
                    mean_ms REAL NOT NULL,
                    p50_ms REAL NOT NULL,
                    p95_ms REAL NOT NULL,
                    min_ms REAL NOT NULL,
                    max_ms REAL NOT NULL,
                    measured_at TEXT NOT NULL,
                    evidence TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telemetry_id INTEGER NOT NULL UNIQUE REFERENCES telemetry(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','acknowledged','resolved')),
                    note TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_active
                    ON alerts(status, updated_at DESC) WHERE status != 'resolved';
                CREATE TABLE IF NOT EXISTS alert_rules (
                    device_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    anomaly_threshold REAL NOT NULL CHECK(anomaly_threshold BETWEEN 0.1 AND 0.99),
                    temperature_threshold_c REAL NOT NULL CHECK(temperature_threshold_c BETWEEN 20 AND 120),
                    retention_days INTEGER NOT NULL DEFAULT 30 CHECK(retention_days BETWEEN 1 AND 3650),
                    updated_at TEXT NOT NULL
                );
                """
            )

    def save_event(self, event: EdgeEvent, create_alert: bool = True) -> int:
        row = event.model_dump(mode="json")
        telemetry = row["telemetry"]
        inference = row["inference"]
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO telemetry (
                    device_id, measured_at, received_at, temperature_c, accel_rms_g,
                    anomaly_score, is_anomaly, reason_codes, engine, model_version, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    telemetry["device_id"], telemetry["ts"], row["received_at"],
                    telemetry["temperature_c"], telemetry["accel_rms_g"],
                    inference["score"], int(inference["is_anomaly"]),
                    json.dumps(inference["reason_codes"]), inference["engine"],
                    inference["model_version"], inference["latency_ms"],
                ),
            )
            telemetry_id = int(cursor.lastrowid)
            if inference["is_anomaly"] and create_alert:
                connection.execute(
                    "INSERT OR IGNORE INTO alerts (telemetry_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (telemetry_id, row["received_at"], row["received_at"]),
                )
            return telemetry_id

    def save_benchmark(self, result: BenchmarkResult) -> int:
        row = result.model_dump(mode="json")
        columns = list(row)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO benchmark_runs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
            return int(cursor.lastrowid)

    def history(self, device_id: str | None = None, limit: int = 120) -> list[dict]:
        query = "SELECT * FROM telemetry"
        params: list[object] = []
        if device_id:
            query += " WHERE device_id = ?"
            params.append(device_id)
        query += " ORDER BY measured_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, params)]
        for row in rows:
            row["is_anomaly"] = bool(row["is_anomaly"])
            row["reason_codes"] = json.loads(row["reason_codes"])
        return rows

    def anomalies(self, device_id: str | None = None, limit: int = 50) -> list[dict]:
        query = "SELECT * FROM telemetry WHERE is_anomaly = 1"
        params: list[object] = []
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        query += " ORDER BY measured_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, params)]
        for row in rows:
            row["is_anomaly"] = True
            row["reason_codes"] = json.loads(row["reason_codes"])
        return rows

    def benchmarks(self, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM benchmark_runs ORDER BY measured_at DESC LIMIT ?", (limit,)
            )]

    def summary(self) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) samples, SUM(is_anomaly) anomalies,
                COUNT(DISTINCT device_id) devices, MAX(measured_at) latest_at FROM telemetry"""
            ).fetchone()
        return {
            "samples": row["samples"] or 0,
            "anomalies": row["anomalies"] or 0,
            "devices": row["devices"] or 0,
            "latest_at": row["latest_at"],
        }

    def alert_page(self, status: str | None = None, cursor: int | None = None, limit: int = 30) -> dict:
        query = """SELECT a.id alert_id, a.status, a.note, a.actor, a.created_at, a.updated_at,
            t.* FROM alerts a JOIN telemetry t ON t.id = a.telemetry_id WHERE 1=1"""
        params: list[object] = []
        if status:
            query += " AND a.status = ?"
            params.append(status)
        if cursor:
            query += " AND a.id < ?"
            params.append(cursor)
        query += " ORDER BY a.id DESC LIMIT ?"
        params.append(limit + 1)
        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, params)]
        has_more = len(rows) > limit
        rows = rows[:limit]
        for row in rows:
            row["is_anomaly"] = bool(row["is_anomaly"])
            row["reason_codes"] = json.loads(row["reason_codes"])
        return {"items": rows, "next_cursor": rows[-1]["alert_id"] if has_more else None}

    def update_alert(self, alert_id: int, status: str, note: str, actor: str, updated_at: str) -> dict | None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE alerts SET status=?, note=?, actor=?, updated_at=? WHERE id=?",
                (status, note, actor, updated_at, alert_id),
            )
        page = self.alert_page(limit=500)
        return next((item for item in page["items"] if item["alert_id"] == alert_id), None)

    def get_rule(self, device_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM alert_rules WHERE device_id=?", (device_id,)).fetchone()
        return dict(row) if row else {
            "device_id": device_id, "enabled": True, "anomaly_threshold": 0.7,
            "temperature_threshold_c": 70.0, "retention_days": 30, "updated_at": None,
        }

    def upsert_rule(self, device_id: str, enabled: bool, anomaly_threshold: float,
                    temperature_threshold_c: float, retention_days: int, updated_at: str) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO alert_rules VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET enabled=excluded.enabled,
                anomaly_threshold=excluded.anomaly_threshold,
                temperature_threshold_c=excluded.temperature_threshold_c,
                retention_days=excluded.retention_days, updated_at=excluded.updated_at""",
                (device_id, int(enabled), anomaly_threshold, temperature_threshold_c, retention_days, updated_at),
            )
        rule = self.get_rule(device_id)
        rule["enabled"] = bool(rule["enabled"])
        return rule

    def purge_before(self, cutoff: str) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM telemetry WHERE measured_at < ?", (cutoff,))
            connection.execute("DELETE FROM benchmark_runs WHERE measured_at < ?", (cutoff,))
            return cursor.rowcount

    def ping(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1
