from __future__ import annotations

import asyncio
import csv
import io
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from .hub import WebSocketHub
from .benchmark import run_benchmark
from .inference_engines import InferenceManager
from .mqtt_bridge import MQTTBridge
from .runtime import RuntimeRegistry
from .schemas import AlertRuleUpdate, AlertUpdate, BenchmarkRequest, BenchmarkResult, RuntimeStatus, SimulatorStartRequest, SimulatorState, utc_now
from .simulator import MQTTSimulator
from .store_factory import create_store

ROOT = Path(__file__).resolve().parent.parent


def secret_value(name: str) -> str | None:
    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        return Path(file_path).read_text().strip()
    return os.getenv(name)


MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "data" / "edgesense.db"))
DATABASE_URL = secret_value("DATABASE_URL")
API_KEY = secret_value("API_KEY")
AUTH_SESSION_TTL_SECONDS = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800"))
auth_sessions: dict[str, float] = {}
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))

hub = WebSocketHub()
registry = RuntimeRegistry()
inference_manager = InferenceManager()
store = create_store(DATABASE_URL, DATABASE_PATH)
bridge = MQTTBridge(
    host=MQTT_HOST,
    port=MQTT_PORT,
    hub=hub,
    registry=registry,
    inference_manager=inference_manager,
    store=store,
    username=secret_value("MQTT_USERNAME"),
    password=secret_value("MQTT_PASSWORD"),
    ca_cert=os.getenv("MQTT_CA_CERT"),
    client_cert=os.getenv("MQTT_CLIENT_CERT"),
    client_key=os.getenv("MQTT_CLIENT_KEY"),
)
simulator = MQTTSimulator(bridge, registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from datetime import timedelta
    await asyncio.to_thread(store.purge_before, (utc_now() - timedelta(days=RETENTION_DAYS)).isoformat())
    bridge.start(asyncio.get_running_loop())
    yield
    await simulator.stop()
    bridge.stop()


app = FastAPI(title="EdgeSense Forge Edge Service", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT), name="static")


@app.middleware("http")
async def api_authentication(request, call_next):
    public_paths = {"/api/status", "/api/models", "/api/auth/status", "/api/auth/session", "/health/live", "/health/ready"}
    if API_KEY and request.url.path.startswith("/api/") and request.url.path not in public_paths:
        supplied = request.headers.get("x-api-key", "")
        session = request.cookies.get("edgesense_session", "")
        session_valid = bool(session and auth_sessions.get(session, 0) > time.time())
        if not session_valid and not secrets.compare_digest(supplied, API_KEY):
            return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
    return await call_next(request)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/app.mjs", include_in_schema=False)
async def app_module() -> FileResponse:
    return FileResponse(ROOT / "app.mjs", media_type="text/javascript")


@app.get("/model.mjs", include_in_schema=False)
async def model_module() -> FileResponse:
    return FileResponse(ROOT / "model.mjs", media_type="text/javascript")


@app.get("/styles.css", include_in_schema=False)
async def stylesheet() -> FileResponse:
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/api/status", response_model=RuntimeStatus)
async def status() -> RuntimeStatus:
    return RuntimeStatus(
        service="ready" if bridge.connected else "degraded",
        mqtt_connected=bridge.connected,
        websocket_clients=hub.count,
        simulator=simulator.state,
        broker=f"{MQTT_HOST}:{MQTT_PORT}",
    )


@app.get("/api/auth/status")
async def auth_status() -> dict:
    return {"required": bool(API_KEY)}


@app.post("/api/auth/session")
async def create_auth_session(request: Request) -> JSONResponse:
    if not API_KEY:
        return JSONResponse({"authenticated": True, "required": False})
    supplied = request.headers.get("x-api-key", "")
    if not secrets.compare_digest(supplied, API_KEY):
        return JSONResponse({"detail": "invalid API key"}, status_code=401)
    now = time.time()
    for token, expires_at in list(auth_sessions.items()):
        if expires_at <= now:
            auth_sessions.pop(token, None)
    token = secrets.token_urlsafe(32)
    auth_sessions[token] = now + AUTH_SESSION_TTL_SECONDS
    response = JSONResponse({"authenticated": True, "expires_in": AUTH_SESSION_TTL_SECONDS})
    response.set_cookie("edgesense_session", token, max_age=AUTH_SESSION_TTL_SECONDS,
                        httponly=True, samesite="strict", secure=request.url.scheme == "https")
    return response


@app.get("/health/live")
async def health_live() -> dict:
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    database_ready = await asyncio.to_thread(store.ping)
    ready = database_ready and bridge.connected
    return JSONResponse({"status": "ready" if ready else "degraded", "database": database_ready,
                         "mqtt": bridge.connected}, status_code=200 if ready else 503)


@app.get("/api/models")
async def models() -> dict:
    return {"active_engine": inference_manager.active.name, "engines": inference_manager.engines()}


@app.post("/api/benchmark", response_model=BenchmarkResult)
async def benchmark(request: BenchmarkRequest) -> BenchmarkResult:
    result = await asyncio.to_thread(run_benchmark, inference_manager, request)
    await asyncio.to_thread(store.save_benchmark, result)
    return result


@app.get("/api/history")
async def history(device_id: str | None = None, limit: int = 120) -> dict:
    return {"items": await asyncio.to_thread(store.history, device_id, min(max(limit, 1), 1000))}


@app.get("/api/anomalies")
async def anomalies(device_id: str | None = None, limit: int = 50) -> dict:
    return {"items": await asyncio.to_thread(store.anomalies, device_id, min(max(limit, 1), 500))}


@app.get("/api/benchmarks")
async def benchmarks(limit: int = 50) -> dict:
    return {"items": await asyncio.to_thread(store.benchmarks, min(max(limit, 1), 500))}


@app.get("/api/history/summary")
async def history_summary() -> dict:
    return await asyncio.to_thread(store.summary)


@app.get("/api/alerts")
async def alerts(status: str | None = None, cursor: int | None = None, limit: int = 30) -> dict:
    if status not in (None, "open", "acknowledged", "resolved"):
        raise HTTPException(status_code=422, detail="invalid alert status")
    return await asyncio.to_thread(store.alert_page, status, cursor, min(max(limit, 1), 100))


@app.patch("/api/alerts/{alert_id}")
async def update_alert(alert_id: int, request: AlertUpdate) -> dict:
    updated = await asyncio.to_thread(
        store.update_alert, alert_id, request.status, request.note, request.actor, utc_now().isoformat()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="alert not found")
    return updated


@app.get("/api/alerts/export.csv")
async def export_alerts(status: str | None = None) -> StreamingResponse:
    page = await asyncio.to_thread(store.alert_page, status, None, 10000)
    output = io.StringIO()
    fields = ["alert_id", "status", "device_id", "measured_at", "temperature_c", "accel_rms_g",
              "anomaly_score", "reason_codes", "note", "actor", "updated_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in page["items"]:
        item = dict(item); item["reason_codes"] = "|".join(item["reason_codes"])
        writer.writerow(item)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=edgesense-alerts.csv"})


@app.get("/api/rules/{device_id}")
async def get_rule(device_id: str) -> dict:
    return await asyncio.to_thread(store.get_rule, device_id)


@app.put("/api/rules/{device_id}")
async def put_rule(device_id: str, request: AlertRuleUpdate) -> dict:
    rule = await asyncio.to_thread(store.upsert_rule, device_id, request.enabled,
        request.anomaly_threshold, request.temperature_threshold_c, request.retention_days, utc_now().isoformat())
    registry.configure(device_id, anomaly_threshold=request.anomaly_threshold,
                       temperature_threshold_c=request.temperature_threshold_c)
    return rule


@app.post("/api/retention/run")
async def run_retention(days: int = RETENTION_DAYS) -> dict:
    from datetime import timedelta
    if not 1 <= days <= 3650:
        raise HTTPException(status_code=422, detail="days must be between 1 and 3650")
    cutoff = (utc_now() - timedelta(days=days)).isoformat()
    deleted = await asyncio.to_thread(store.purge_before, cutoff)
    return {"deleted_telemetry": deleted, "cutoff": cutoff}


@app.post("/api/simulator/start", response_model=SimulatorState)
async def start_simulator(request: SimulatorStartRequest) -> SimulatorState:
    try:
        return await simulator.start(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/simulator/stop", response_model=SimulatorState)
async def stop_simulator() -> SimulatorState:
    return await simulator.stop()


@app.post("/api/simulator/reset", response_model=SimulatorState)
async def reset_simulator() -> SimulatorState:
    return await simulator.reset()


@app.websocket("/ws/events")
async def events(websocket: WebSocket) -> None:
    protocols = [value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    session = websocket.cookies.get("edgesense_session", "")
    if API_KEY and not (session and auth_sessions.get(session, 0) > time.time()):
        await websocket.close(code=4401)
        return
    await hub.connect(websocket, subprotocol="edgesense" if protocols and protocols[0] == "edgesense" else None)
    await websocket.send_json({"type": "connection", "status": "connected"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)
